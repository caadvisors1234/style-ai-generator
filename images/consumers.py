"""
WebSocket consumers for real-time image conversion progress tracking.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from .models import ImageConversion


class ImageConversionConsumer(AsyncWebsocketConsumer):
    """
    WebSocketコンシューマー
    画像変換の進捗をリアルタイムで配信
    """

    async def connect(self):
        """
        WebSocket接続時の処理
        """
        # URLパラメータから変換IDを取得
        self.conversion_id = self.scope['url_route']['kwargs']['conversion_id']
        self.conversion_group_name = f'conversion_{self.conversion_id}'

        # 認証確認
        user = self.scope.get('user', AnonymousUser())
        if user.is_anonymous:
            await self.close()
            return

        # 変換履歴の所有者確認
        is_owner = await self.check_conversion_ownership(user.id, self.conversion_id)
        if not is_owner:
            await self.close()
            return

        # グループに参加
        await self.channel_layer.group_add(
            self.conversion_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        """
        WebSocket切断時の処理

        Args:
            close_code: 切断コード
        """
        # グループから退出
        if hasattr(self, 'conversion_group_name'):
            await self.channel_layer.group_discard(
                self.conversion_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """
        クライアントからメッセージを受信

        Args:
            text_data: 受信したJSONテキスト
        """
        # このコンシューマーは受信専用なので何もしない
        pass

    async def conversion_progress(self, event):
        """
        変換進捗メッセージをクライアントに送信

        Args:
            event: 進捗イベントデータ
        """
        message_data = {
            'type': 'progress',
            'message': event['message'],
            'progress': event['progress'],
            'status': event['status']
        }
        # currentとtotalが含まれている場合は追加
        if 'current' in event:
            message_data['current'] = event['current']
            message_data['currentCount'] = event['current']  # 互換性のため
        if 'total' in event:
            message_data['total'] = event['total']
            message_data['totalCount'] = event['total']  # 互換性のため
        # フォールバック情報があれば付加
        if event.get('fallback'):
            message_data['fallback'] = True
            message_data['requested_model'] = event.get('requested_model')
            message_data['used_model'] = event.get('used_model')
            message_data['refund'] = event.get('refund')
            message_data['usage_consumed'] = event.get('usage_consumed')
        await self.send(text_data=json.dumps(message_data))

    async def conversion_completed(self, event):
        """
        変換完了メッセージをクライアントに送信

        Args:
            event: 完了イベントデータ
        """
        await self.send(text_data=json.dumps({
            'type': 'completed',
            'message': event['message'],
            'images': event['images']
        }))

    async def conversion_failed(self, event):
        """
        変換失敗メッセージをクライアントに送信

        Args:
            event: 失敗イベントデータ
        """
        await self.send(text_data=json.dumps({
            'type': 'failed',
            'message': event['message'],
            'error': event.get('error', '')
        }))

    async def conversion_cancelled(self, event):
        """
        変換キャンセルメッセージをクライアントに送信

        Args:
            event: キャンセルイベントデータ
        """
        await self.send(text_data=json.dumps({
            'type': 'cancelled',
            'message': event['message']
        }))

    @database_sync_to_async
    def check_conversion_ownership(self, user_id, conversion_id):
        """
        変換履歴の所有者確認

        Args:
            user_id (int): ユーザーID
            conversion_id (int): 変換履歴ID

        Returns:
            bool: 所有者の場合True
        """
        try:
            conversion = ImageConversion.objects.get(
                id=conversion_id,
                user_id=user_id,
                is_deleted=False
            )
            return True
        except ImageConversion.DoesNotExist:
            return False
