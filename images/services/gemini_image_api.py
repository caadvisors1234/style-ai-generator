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
    Gemini 2.5 Flash Imageを使用した画像生成サービス

    Vertex AI経由でgemini-2.5-flash-imageモデルを使用
    """

    # 使用するモデル
    MODEL_NAME = "gemini-2.5-flash-image"
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
            location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
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
                f"location={location}, model={cls.MODEL_NAME}"
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
        aspect_ratio: str = None
    ) -> List[Dict[str, Any]]:
        """
        参照画像を元に新しい画像を生成

        Args:
            original_image_path: 元画像のパス
            prompt: 変換プロンプト
            generation_count: 生成枚数（1-10）
            aspect_ratio: アスペクト比（例: "4:3"）

        Returns:
            生成結果のリスト
            [
                {
                    "image_data": bytes,
                    "description": str,
                    "generation_number": int
                },
                ...
            ]

        Raises:
            GeminiImageAPIError: 画像生成に失敗した場合
        """
        try:
            # クライアント初期化
            client = cls.initialize_client()

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

                    response = client.models.generate_content(
                        model=cls.MODEL_NAME,
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
                            'aspect_ratio': aspect_ratio
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

            return results

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
        # バリエーションのための追加指示
        variation_instructions = {
            1: "ベースとなるスタイルを忠実に再現し、バランスの良いサロンスタンダードを目指してください。",
            2: "柔らかい光とやわらかなトーンで、明るく女性らしい仕上がりにしてください。",
            3: "ハイファッション誌のビューティー特集のように、高級感とコントラストを強調してください。",
            4: "クールで都会的な雰囲気を出し、エッジの効いた質感表現とライティングにしてください。",
            5: "自然光を活かしたリラックス感のある雰囲気で、ナチュラルな色味を大切にしてください。",
        }

        # デフォルトの指示（6番目以降）
        default_instruction = (
            f"バリエーション{generation_number}として、"
            "プロが提案する別案に感じられる独自のアレンジを加えてください。"
        )

        variation_hint = variation_instructions.get(generation_number, default_instruction)

        base_prompt = f"""
元画像の人物を参照し、美容室の広告・カタログに掲載できる高品質なスタイル写真を生成してください。

### 入力情報
- 参照画像: ユーザーがアップロードした元画像。構図・顔の向き・身体のバランスを大きく崩さないでください。
- ユーザー希望スタイル: {user_prompt}
- バリエーション指示: {variation_hint}

### クリエイティブ方針
1. 被写体の顔立ち・骨格・肌トーン・体型・手指を保持し、自然な髪の生え際や首肩のラインを保ってください。
2. 髪型・ヘアカラー・メイク・衣装はユーザー希望と整合させつつ、プロのスタイリストが提案したかのような完成度で表現してください。
3. プロ仕様のポートレート撮影を想定し、85mm相当のレンズで浅めの被写界深度、瞳にキャッチライトを入れてください。
4. 髪の毛一本一本の質感、ツヤ、流れを丁寧に描写し、毛先の破綻やぼやけを避けてください。

### ライティングと背景
- 3点照明やソフトボックスを使った立体的なライティングで、肌と髪を美しく再現してください。
- 背景はサロンスタジオや高級感のある無地背景など、スタイルを際立たせるシンプルで上質なものにしてください。
- 背景のボケや反射は自然な範囲に抑え、被写体の輪郭が溶け込まないようにしてください。

### 色彩と仕上げ
- ホワイトバランスを整え、肌は健康的で自然な色味に、髪色はスタイル指示に沿って艶や奥行きを出してください。
- 過剰なHDR、ビネット、ノイズ、粒状感は避け、高解像かつクリーンな仕上がりを目指してください。
- 露出オーバー／アンダーを避け、髪のハイライト・シャドウのディテールを保持してください。

### 品質要件
- 4K相当の解像度を想定したシャープでノイズの少ない出力。
- 手や指が写る場合は自然な本数と形状を維持してください。
- 文字、透かし、ロゴ、余計な装飾は入れないでください。

### 禁止事項
- 顔・身体の歪み、手足の融合や増殖、極端な比率の崩れ。
- カートゥーン／油絵調など意図しない画風への極端な変換。
- ブレ、モーションアーティファクト、低解像度、過度なフィルター。

### 出力
- 参照画像の印象を活かしつつ、サロンの PR・カタログ・SNS で即使用できる完成度の1枚を生成してください。
- 被写体をフレーム中央に配置し、髪型全体が理解できるよう収まりを調整してください。
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
            location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')

            # 簡単なテスト生成
            response = client.models.generate_content(
                model=cls.MODEL_NAME,
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
                "message": "Gemini 2.5 Flash Image APIへの接続に成功しました" if has_image else "接続は成功しましたが、画像生成に失敗しました",
                "model_name": cls.MODEL_NAME,
                "project_id": project_id,
                "location": location,
                "has_image": has_image
            }

        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return {
                "success": False,
                "message": f"接続テストに失敗しました: {str(e)}",
                "model_name": cls.MODEL_NAME,
                "project_id": os.getenv('GOOGLE_CLOUD_PROJECT', 'Not set'),
                "location": os.getenv('GOOGLE_CLOUD_LOCATION', 'Not set')
            }
