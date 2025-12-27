/**
 * WebSocket接続管理ユーティリティ
 * Django Channels WebSocket接続を管理し、リアルタイム進捗更新を提供
 */
(() => {
  'use strict';

  /**
   * WebSocket接続を管理するクラス
   */
  class ConversionWebSocket {
    constructor(conversionId, options = {}) {
      this.conversionId = conversionId;
      this.options = {
        reconnectInterval: options.reconnectInterval || 1000, // 1秒間隔で再接続試行
        maxReconnectAttempts: options.maxReconnectAttempts || 3, // 3回失敗したらポーリングへ
        enableFallback: options.enableFallback !== false, // デフォルトで有効
        fallbackPollInterval: options.fallbackPollInterval || 2000, // 2秒間隔でポーリング
        ...options,
      };

      this.ws = null;
      this.reconnectAttempts = 0;
      this.isManualClose = false;
      this.isConnected = false;
      this.fallbackTimer = null;
      this.useFallback = false;

      // イベントハンドラー
      this.handlers = {
        progress: [],
        completed: [],
        failed: [],
        cancelled: [],
        error: [],
        connect: [],
        disconnect: [],
      };
    }

    /**
     * WebSocket接続を開始
     */
    connect() {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        console.log('[WebSocket] WebSocket already connected');
        return;
      }

      this.isManualClose = false;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/conversion/${this.conversionId}/`;

      try {
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          console.log('[WebSocket] WebSocket connected');
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.useFallback = false;
          if (this.fallbackTimer) {
            clearInterval(this.fallbackTimer);
            this.fallbackTimer = null;
          }
          this.emit('connect');
        };

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
          } catch (error) {
            console.error('[WebSocket] Failed to parse WebSocket message:', error);
            // パースエラーは内部で処理（ユーザー通知は不要）
          }
        };

        this.ws.onerror = (error) => {
          console.error('[WebSocket] WebSocket error:', error);
          this.emit('error', error);
        };

        this.ws.onclose = (event) => {
          console.log('[WebSocket] WebSocket closed', event.code, event.reason);
          this.isConnected = false;
          this.emit('disconnect', event);

          // 手動クローズでない場合、再接続を試みる
          if (!this.isManualClose && this.reconnectAttempts < this.options.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`[WebSocket] Attempting to reconnect (${this.reconnectAttempts}/${this.options.maxReconnectAttempts})...`);
            setTimeout(() => this.connect(), this.options.reconnectInterval);
          } else if (!this.isManualClose && this.options.enableFallback) {
            // 再接続に失敗した場合、フォールバック（ポーリング）に切り替え
            console.log('[WebSocket] Switching to fallback polling mode');
            this.useFallback = true;
            this.startFallbackPolling();
          }
        };
      } catch (error) {
        console.error('[WebSocket] Failed to create WebSocket connection:', error);
        if (this.options.enableFallback) {
          this.useFallback = true;
          this.startFallbackPolling();
        }
      }
    }

    /**
     * WebSocket接続を閉じる
     */
    disconnect() {
      this.isManualClose = true;
      if (this.ws) {
        this.ws.close();
        this.ws = null;
      }
      if (this.fallbackTimer) {
        clearInterval(this.fallbackTimer);
        this.fallbackTimer = null;
      }
    }

    /**
     * メッセージを処理
     */
    handleMessage(data) {
      const { type } = data;

      switch (type) {
        case 'progress':
          this.emit('progress', {
            message: data.message,
            progress: data.progress,
            status: data.status,
            current: data.current,
            currentCount: data.currentCount,
            total: data.total,
            totalCount: data.totalCount,
            fallback: data.fallback,
            requested_model: data.requested_model,
            used_model: data.used_model,
            refund: data.refund,
            usage_consumed: data.usage_consumed,
          });
          break;

        case 'completed':
          this.emit('completed', {
            message: data.message,
            images: data.images || [],
            success_count: data.success_count,
            requested_count: data.requested_count,
          });
          break;

        case 'failed':
          this.emit('failed', {
            message: data.message,
            error: data.error || '',
          });
          break;

        case 'cancelled':
          this.emit('cancelled', {
            message: data.message,
          });
          break;

        default:
          console.warn('[WebSocket] Unknown message type:', type);
      }
    }

    /**
     * フォールバック（ポーリング）を開始
     */
    startFallbackPolling() {
      if (this.fallbackTimer) {
        return; // 既に開始されている
      }

      console.log('[WebSocket] Starting fallback polling');
      this.fallbackTimer = setInterval(async () => {
        try {
          const data = await APIClient.get(`/api/v1/convert/${this.conversionId}/status/`);
          const conversion = data.conversion;

          // 進捗情報を計算
          const total = conversion.generation_count || 0;
          const current = conversion.current_count || 0;
          let progress = 10;
          if (total > 0) {
            const ratio = Math.min(99, Math.round((current / total) * 100));
            progress = Math.max(progress, ratio);
          }
          if (conversion.status === 'completed' || conversion.status === 'failed') {
            progress = 100;
          }

          // WebSocketと同じ形式でイベントを発火
          if (conversion.status === 'processing') {
            this.emit('progress', {
              message: '画像変換を実行中...',
              progress: progress,
              status: 'processing',
              current: current,
              currentCount: current,
              total: total,
              totalCount: total,
            });
          } else if (conversion.status === 'completed') {
            this.emit('completed', {
              message: '画像変換が完了しました',
              images: data.images || [],
            });
            this.disconnect();
          } else if (conversion.status === 'failed') {
            this.emit('failed', {
              message: conversion.error_message || '画像変換に失敗しました',
              error: conversion.error_message || '',
            });
            this.disconnect();
          } else if (conversion.status === 'cancelled') {
            this.emit('cancelled', {
              message: '変換をキャンセルしました',
            });
            this.disconnect();
          }
        } catch (error) {
          // ポーリングエラーは静かに処理（連続エラーの場合は別途対応）
          console.error('[WebSocket] Fallback polling error:', error);
        }
      }, this.options.fallbackPollInterval);
    }

    /**
     * イベントリスナーを登録
     */
    on(event, handler) {
      if (this.handlers[event]) {
        this.handlers[event].push(handler);
      }
    }

    /**
     * イベントリスナーを削除
     */
    off(event, handler) {
      if (this.handlers[event]) {
        const index = this.handlers[event].indexOf(handler);
        if (index > -1) {
          this.handlers[event].splice(index, 1);
        }
      }
    }

    /**
     * イベントを発火
     */
    emit(event, data) {
      if (this.handlers[event]) {
        this.handlers[event].forEach((handler) => {
          try {
            handler(data);
          } catch (error) {
            console.error(`[WebSocket] Error in ${event} handler:`, error);
          }
        });
      }
    }
  }

  /**
   * 複数の変換を管理するWebSocketマネージャー
   */
  class MultipleConversionWebSocket {
    constructor(conversionIds, options = {}) {
      this.conversionIds = conversionIds;
      this.options = options;
      this.connections = new Map();
      this.handlers = {
        progress: [],
        completed: [],
        failed: [],
        cancelled: [],
        error: [],
      };
    }

    /**
     * 全ての接続を開始
     */
    connect() {
      this.conversionIds.forEach((id) => {
        const ws = new ConversionWebSocket(id, this.options);

        // 各イベントを転送
        ws.on('progress', (data) => {
          this.emit('progress', { conversionId: id, ...data });
        });
        ws.on('completed', (data) => {
          this.emit('completed', { conversionId: id, ...data });
        });
        ws.on('failed', (data) => {
          this.emit('failed', { conversionId: id, ...data });
        });
        ws.on('cancelled', (data) => {
          this.emit('cancelled', { conversionId: id, ...data });
        });
        ws.on('error', (data) => {
          this.emit('error', { conversionId: id, ...data });
        });

        ws.connect();
        this.connections.set(id, ws);
      });
    }

    /**
     * 全ての接続を閉じる
     */
    disconnect() {
      this.connections.forEach((ws) => ws.disconnect());
      this.connections.clear();
    }

    /**
     * 特定の変換の接続を閉じる
     */
    disconnectConversion(conversionId) {
      const ws = this.connections.get(conversionId);
      if (ws) {
        ws.disconnect();
        this.connections.delete(conversionId);
      }
    }

    /**
     * イベントリスナーを登録
     */
    on(event, handler) {
      if (this.handlers[event]) {
        this.handlers[event].push(handler);
      }
    }

    /**
     * イベントリスナーを削除
     */
    off(event, handler) {
      if (this.handlers[event]) {
        const index = this.handlers[event].indexOf(handler);
        if (index > -1) {
          this.handlers[event].splice(index, 1);
        }
      }
    }

    /**
     * イベントを発火
     */
    emit(event, data) {
      if (this.handlers[event]) {
        this.handlers[event].forEach((handler) => {
          try {
            handler(data);
          } catch (error) {
            console.error(`[WebSocket] Error in ${event} handler:`, error);
          }
        });
      }
    }
  }

  // グローバルに公開
  window.ConversionWebSocket = ConversionWebSocket;
  window.MultipleConversionWebSocket = MultipleConversionWebSocket;
})();

