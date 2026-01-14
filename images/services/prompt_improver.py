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

    SYSTEM_INSTRUCTION = """あなたは画像生成AIのプロンプト改善の専門家です。
簡易的なプロンプトを、Gemini 2.5 Flash Image で高品質な画像を生成できる詳細なプロンプトに改善してください。

重要な原則:
1. 自然な文章で場面を具体的に描写する
2. 被写体、環境、照明、雰囲気、カメラアングルを含める
3. 肯定的な表現を使う
4. 髪型、髪色、表情、場所、スタイルを明確にする

改善後のプロンプトのみを日本語で出力してください。説明や前置きは不要です。"""

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
                    temperature=0.7,  # クリエイティブだが一貫性のある出力
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
