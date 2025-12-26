"""
Gemini 2.5 Flash Image API Service

Vertex AI経由でGemini 2.5 Flash Imageを使用した画像生成サービス
"""
import os
import logging
from typing import List, Dict, Any
from pathlib import Path
from PIL import Image as PILImage
from google import genai
from google.genai import types
from django.conf import settings


logger = logging.getLogger(__name__)


class GeminiImageAPIError(Exception):
    """Gemini Image API関連のエラー"""
    pass


class GeminiImageAPIService:
    """
    Gemini系画像生成サービス
    """

    # モデル設定
    DEFAULT_MODEL = "gemini-2.5-flash-image"
    MODEL_NAME = DEFAULT_MODEL  # backward compatibility
    SUPPORTED_MODELS = {
        "gemini-2.5-flash-image",
        "gemini-3-pro-image-preview",
    }
    ORIGINAL_ASPECT_RATIO = "original"

    # サポートされるアスペクト比
    SUPPORTED_ASPECT_RATIOS = [
        ORIGINAL_ASPECT_RATIO,
        "1:1", "3:4", "4:3", "9:16", "16:9",
        "3:2", "2:3", "21:9", "9:21", "4:5"
    ]

    # デフォルトのアスペクト比
    DEFAULT_ASPECT_RATIO = ORIGINAL_ASPECT_RATIO

    @classmethod
    def initialize_client(cls) -> genai.Client:
        """
        Vertex AI経由のGenAIクライアントを初期化

        Returns:
            genai.Client: 初期化されたクライアント

        Raises:
            GeminiImageAPIError: 初期化に失敗した場合
        """
        try:
            # 環境変数から設定を取得
            project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
            location = os.getenv('GOOGLE_CLOUD_LOCATION', 'global')
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

            # バリデーション
            if not project_id:
                raise GeminiImageAPIError("GOOGLE_CLOUD_PROJECTが設定されていません")

            if not credentials_path or not os.path.exists(credentials_path):
                raise GeminiImageAPIError(
                    f"GCP認証情報ファイルが見つかりません: {credentials_path}"
                )

            # Vertex AI経由でクライアント初期化
            client = genai.Client(
                vertexai=True,
                project=project_id,
                location=location
            )

            logger.info(
                f"Gemini Image API initialized: project={project_id}, "
                f"location={location}, default_model={cls.DEFAULT_MODEL}"
            )

            return client

        except Exception as e:
            logger.error(f"Failed to initialize Gemini Image API: {str(e)}")
            raise GeminiImageAPIError(f"クライアントの初期化に失敗しました: {str(e)}")

    @classmethod
    def load_image(cls, image_path: str) -> bytes:
        """
        画像ファイルを読み込む

        Args:
            image_path: 画像ファイルのパス（MEDIA_ROOT相対または絶対パス）

        Returns:
            bytes: 画像データ

        Raises:
            GeminiImageAPIError: 画像読み込みに失敗した場合
        """
        try:
            # 絶対パスに変換
            if not image_path.startswith('/'):
                full_path = os.path.join(settings.MEDIA_ROOT, image_path)
            else:
                full_path = image_path

            if not os.path.exists(full_path):
                raise GeminiImageAPIError(f"画像ファイルが見つかりません: {full_path}")

            # 画像を読み込む
            with open(full_path, 'rb') as f:
                image_data = f.read()

            # 画像サイズを確認（オプション）
            img = PILImage.open(full_path)
            logger.info(
                f"Image loaded: {full_path}, size: {img.size}, "
                f"mode: {img.mode}, format: {img.format}"
            )

            return image_data

        except Exception as e:
            logger.error(f"Failed to load image {image_path}: {str(e)}")
            raise GeminiImageAPIError(f"画像の読み込みに失敗しました: {str(e)}")

    @classmethod
    def save_generated_image(
        cls,
        image_data: bytes,
        output_dir: str,
        filename: str
    ) -> str:
        """
        生成された画像を保存

        Args:
            image_data: 画像データ
            output_dir: 出力ディレクトリ（MEDIA_ROOT相対）
            filename: ファイル名

        Returns:
            str: 保存されたファイルのパス（MEDIA_ROOT相対）

        Raises:
            GeminiImageAPIError: 保存に失敗した場合
        """
        try:
            # 出力ディレクトリの絶対パス
            full_output_dir = os.path.join(settings.MEDIA_ROOT, output_dir)
            os.makedirs(full_output_dir, exist_ok=True)

            # ファイルパス
            output_path = os.path.join(full_output_dir, filename)
            relative_path = os.path.join(output_dir, filename)

            # 画像を保存
            with open(output_path, 'wb') as f:
                f.write(image_data)

            # ファイルサイズを確認
            file_size = os.path.getsize(output_path)
            logger.info(f"Image saved: {output_path}, size: {file_size} bytes")

            return relative_path

        except Exception as e:
            logger.error(f"Failed to save image: {str(e)}")
            raise GeminiImageAPIError(f"画像の保存に失敗しました: {str(e)}")

    @classmethod
    def generate_images_from_reference(
        cls,
        original_image_path: str,
        prompt: str,
        generation_count: int = 3,
        aspect_ratio: str = None,
        model_name: str = None,
    ) -> List[Dict[str, Any]]:
        """
        参照画像を元に新しい画像を生成

        Args:
            original_image_path: 元画像のパス
            prompt: 変換プロンプト
            generation_count: 生成枚数（1-10）
            aspect_ratio: アスペクト比（例: "4:3"）

        Returns:
            (results, model_used)
            results: 生成結果のリスト
            [
                {
                    "image_data": bytes,
                    "description": str,
                    "generation_number": int
                },
                ...
            ]
            model_used: 実際に使用したモデル名（フォールバック考慮）

        Raises:
            GeminiImageAPIError: 画像生成に失敗した場合
        """
        try:
            # クライアント初期化
            client = cls.initialize_client()

            # モデル解決（リクエスト単位で固定。各生成ごとに都度試行し、必要に応じてフォールバック）
            requested_model = model_name or cls.DEFAULT_MODEL
            if requested_model not in cls.SUPPORTED_MODELS:
                logger.warning(
                    f"Unsupported model {requested_model}, "
                    f"falling back to {cls.DEFAULT_MODEL}"
                )
                requested_model = cls.DEFAULT_MODEL

            # 元画像を読み込む
            image_data = cls.load_image(original_image_path)

            # アスペクト比の検証・解決
            resolved_aspect_ratio = None
            if aspect_ratio and aspect_ratio not in cls.SUPPORTED_ASPECT_RATIOS:
                logger.warning(
                    f"Unsupported aspect ratio {aspect_ratio}, "
                    f"using default {cls.DEFAULT_ASPECT_RATIO}"
                )
                aspect_ratio = cls.DEFAULT_ASPECT_RATIO
            elif not aspect_ratio:
                aspect_ratio = cls.DEFAULT_ASPECT_RATIO

            if aspect_ratio != cls.ORIGINAL_ASPECT_RATIO:
                resolved_aspect_ratio = aspect_ratio

            results = []

            # 指定回数分生成
            fallback_count = 0

            for i in range(generation_count):
                try:
                    # バリエーション用のプロンプト構築
                    full_prompt = cls._build_variation_prompt(prompt, i + 1)

                    logger.info(
                        f"Generating image {i + 1}/{generation_count} "
                        f"with prompt: {full_prompt[:100]}..."
                    )

                    # 画像生成
                    image_config = None
                    if resolved_aspect_ratio:
                        image_config = types.ImageConfig(
                            aspect_ratio=resolved_aspect_ratio,
                        )

                    def _generate(model_to_use: str):
                        return client.models.generate_content(
                            model=model_to_use,
                        contents=[
                            types.Part.from_bytes(
                                data=image_data,
                                mime_type='image/jpeg'
                            ),
                            full_prompt
                        ],
                        config=types.GenerateContentConfig(
                            response_modalities=['IMAGE'],
                            image_config=image_config,
                            candidate_count=1,
                        ),
                    )

                    try:
                        response = _generate(requested_model)
                        used_model_this_round = requested_model
                    except Exception as api_error:
                        # モデル未許可/未提供の場合はデフォルトモデルへフォールバック（このイテレーションのみ）
                        if requested_model != cls.DEFAULT_MODEL and "NOT_FOUND" in str(api_error):
                            logger.warning(
                                "Model %s not available. Falling back to default %s (iteration %s)",
                                requested_model,
                                cls.DEFAULT_MODEL,
                                i + 1,
                            )
                            response = _generate(cls.DEFAULT_MODEL)
                            used_model_this_round = cls.DEFAULT_MODEL
                            fallback_count += 1
                        else:
                            raise

                    # レスポンスから画像を取得
                    generated_image_data = None
                    description = ""

                    for part in response.parts:
                        if part.text:
                            description = part.text
                        if part.inline_data is not None:
                            generated_image_data = part.inline_data.data

                    if generated_image_data:
                        results.append({
                            'image_data': generated_image_data,
                            'description': description,
                            'generation_number': i + 1,
                            'prompt_used': full_prompt,
                            'aspect_ratio': aspect_ratio,
                            'model_used': used_model_this_round,
                        })
                        logger.info(f"Successfully generated image {i + 1}/{generation_count}")
                    else:
                        logger.warning(f"No image data in response for generation {i + 1}")

                except Exception as e:
                    logger.error(f"Failed to generate image {i + 1}: {str(e)}")
                    # 一部失敗しても続行
                    continue

            if not results:
                raise GeminiImageAPIError("画像の生成に失敗しました")

            logger.info(f"Successfully generated {len(results)} images")

            # すべての生成がフォールバックした場合のみ、実際のモデルとしてデフォルトを返す
            batch_model_used = cls.DEFAULT_MODEL if (fallback_count == generation_count and requested_model != cls.DEFAULT_MODEL) else requested_model
            return results, batch_model_used

        except Exception as e:
            logger.error(f"Image generation failed: {str(e)}")
            raise GeminiImageAPIError(f"画像生成に失敗しました: {str(e)}")

    @classmethod
    def _build_variation_prompt(cls, user_prompt: str, generation_number: int) -> str:
        """
        バリエーション用のプロンプトを構築

        Args:
            user_prompt: ユーザーが入力したプロンプト
            generation_number: 生成番号（1-based）

        Returns:
            構築されたプロンプト
        """
        # バリエーション指示（AIにバリエーションを任せる）
        if generation_number > 1:
            variation_hint = f"バリエーション{generation_number}として、ユーザープロンプトに基づき異なるアプローチや表現で生成してください。"
        else:
            variation_hint = None

        # 最低限のシステムプロンプト
        base_prompt = f"""
参照画像を元に、ユーザーの指示に従って高品質な画像を生成してください。

### 入力情報
- 参照画像: ユーザーがアップロードした元画像
- ユーザー指示: {user_prompt}
{f"- バリエーション: {variation_hint}" if variation_hint else ""}
"""
        return base_prompt.strip()

    @classmethod
    def test_connection(cls) -> Dict[str, Any]:
        """
        Gemini 2.5 Flash Image APIへの接続テスト

        Returns:
            テスト結果
            {
                "success": bool,
                "message": str,
                "model_name": str,
                "project_id": str,
                "location": str
            }
        """
        try:
            client = cls.initialize_client()

            project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
            location = os.getenv('GOOGLE_CLOUD_LOCATION', 'global')

            # 簡単なテスト生成
            response = client.models.generate_content(
                model=cls.DEFAULT_MODEL,
                contents="a simple test image of a red circle",
                config=types.GenerateContentConfig(
                    response_modalities=['IMAGE'],
                    image_config=types.ImageConfig(
                        aspect_ratio='1:1',
                    ),
                    candidate_count=1,
                ),
            )

            # 画像が生成されたか確認
            has_image = any(part.inline_data is not None for part in response.parts)

            return {
                "success": has_image,
                "message": "Gemini Image APIへの接続に成功しました" if has_image else "接続は成功しましたが、画像生成に失敗しました",
                "model_name": cls.DEFAULT_MODEL,
                "project_id": project_id,
                "location": location,
                "has_image": has_image
            }

        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return {
                "success": False,
                "message": f"接続テストに失敗しました: {str(e)}",
                "model_name": cls.DEFAULT_MODEL,
                "project_id": os.getenv('GOOGLE_CLOUD_PROJECT', 'Not set'),
                "location": os.getenv('GOOGLE_CLOUD_LOCATION', 'Not set')
            }
