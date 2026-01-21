"""
プロンプト改善サービス

Google Gemini 2.5 Flashを使用して、ユーザー入力プロンプトを
画像生成に最適化されたプロンプトに改善する。
"""

import logging
from typing import Optional
from google import genai
from google.genai import types
from django.conf import settings


logger = logging.getLogger(__name__)


class PromptImproverError(Exception):
    """プロンプト改善サービスのエラー"""
    pass


class PromptImproverService:
    """
    Gemini 2.5 Flashを使用したプロンプト改善サービス

    NanoBanana (Gemini 2.5 Flash Image) のベストプラクティスに則り、
    ユーザー入力を高品質な画像生成プロンプトに変換する。
    """

    SYSTEM_INSTRUCTION = """あなたは最新画像生成モデルのプロンプトエンジニアです。
ユーザーの入力したアイデアを、同モデルの性能を最大化する「日本語の最適化プロンプト」に変換して出力してください。

## ベストプラクティス
1. **構造化**: 画像生成モデルは情報を整理して伝えると推論能力が向上します。プロンプトを【主題】【構図】【照明】【スタイル】などの要素に区切って記述してください。
2. **解像度と品質**: 「4K」「高解像度」「緻密なディテール」などの品質指定を含め、モデルの表現力を引き出してください。
3. **推論の活用**: 「～のように見える」「～な雰囲気で」といった文脈的な指示も、具体的な視覚表現に変換して記述してください。

## 厳守事項
- **出力は改善後のプロンプトのみ**: 解説、挨拶、前置きは一切出力しないでください。
- **指示の忠実性**: ユーザーが明示的に指定していない要素（特定の髪型、顔立ち、服装、色など）は**絶対に変更・追加しないでください**。未指定部分はモデルの創造性に委ねるか、一般的で邪魔にならない表現に留めてください。
- **言語**: 画像生成モデルの高い言語理解力を活かすため、**流暢かつ詳細な日本語**で出力してください。

## 出力フォーマット
以下のような形式で出力してください（内容はユーザーの意図に合わせて最適化すること）：

【主題】
(被写体の詳細、行動、表情、服装など。ユーザー指定を最優先し、不足情報を補完)

【背景・状況】
(場所、環境)

【構図・カメラ】
(アングル、距離、レンズ効果、フォーカス)

【照明・雰囲気】
(光の向き、色温度、全体のムード)

【スタイル・品質】
(フォトリアリスティック等のスタイル指定。4K、高画質等の品質タグ)"""

    def __init__(self, api_key: str):
        """
        Args:
            api_key: Google AI API key
        """
        self.api_key = api_key
        self.client = None

    def initialize_client(self) -> None:
        """Gemini APIクライアントを初期化"""
        try:
            self.client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(api_version='v1alpha')
            )
            logger.info("Gemini API client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini API client: {e}")
            raise PromptImproverError(f"APIクライアントの初期化に失敗しました: {e}")

    def improve_prompt(self, user_prompt: str) -> str:
        """
        ユーザー入力プロンプトを改善する

        Args:
            user_prompt: ユーザーが入力した元のプロンプト

        Returns:
            改善されたプロンプト（日本語）

        Raises:
            PromptImproverError: API呼び出しに失敗した場合
        """
        if not user_prompt or not user_prompt.strip():
            raise PromptImproverError("プロンプトが空です")

        if not self.client:
            self.initialize_client()

        try:
            logger.info(f"Improving prompt: {user_prompt[:100]}...")

            # プロンプト改善リクエスト
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"以下のプロンプトを画像生成に最適化してください:\n\n{user_prompt}",
                config=types.GenerateContentConfig(
                    temperature=0.8,
                    max_output_tokens=6000,
                    top_p=0.95,
                    top_k=40,
                    system_instruction=self.SYSTEM_INSTRUCTION,
                )
            )

            improved_prompt = response.text.strip()

            if not improved_prompt:
                logger.error("Gemini API returned empty response")
                raise PromptImproverError("改善されたプロンプトの生成に失敗しました")

            # レスポンス詳細をログ出力
            logger.info(f"Successfully improved prompt: {improved_prompt[:100]}...")
            logger.info(f"Input tokens: {response.usage_metadata.prompt_token_count}")
            logger.info(f"Output tokens: {response.usage_metadata.candidates_token_count}")
            logger.info(f"Total tokens: {response.usage_metadata.total_token_count}")

            # finish_reasonを確認（途中で切れていないか）
            if hasattr(response, 'candidates') and response.candidates:
                finish_reason = response.candidates[0].finish_reason
                logger.info(f"Finish reason: {finish_reason}")
                if finish_reason == 'MAX_TOKENS':
                    logger.warning("Response was truncated due to max_output_tokens limit")

            return improved_prompt

        except Exception as e:
            logger.error(f"Failed to improve prompt: {e}")
            raise PromptImproverError(f"プロンプトの改善に失敗しました: {e}")

    def test_connection(self) -> bool:
        """
        APIの接続テスト

        Returns:
            接続が成功した場合はTrue
        """
        try:
            if not self.client:
                self.initialize_client()

            # シンプルなテストリクエスト
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents='Test connection'
            )

            return bool(response.text)
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
