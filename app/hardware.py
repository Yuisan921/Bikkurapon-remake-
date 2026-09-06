"""コイン投入検知とカプセル排出用サーボの制御。

Raspberry Pi 上で gpiozero が実際の GPIO を掴めた場合は実機バックエンドを、
それ以外(開発用PCなど)ではログ出力のみのモックバックエンドを使う。
"""

import logging
import time

logger = logging.getLogger(__name__)


class HardwareController:
    def __init__(self, settings, on_coin_inserted):
        self.settings = settings
        self.on_coin_inserted = on_coin_inserted
        self._backend = self._build_backend()

    def _build_backend(self):
        mock_mode = self.settings.get("mock_mode", "auto")
        if mock_mode == "force_mock":
            return _MockBackend(self.settings, self.on_coin_inserted)
        try:
            return _GpioBackend(self.settings, self.on_coin_inserted)
        except Exception as exc:  # noqa: BLE001 - 実機初期化失敗の理由は多岐にわたる
            if mock_mode == "force_real":
                raise
            logger.warning("実機GPIOを初期化できなかったためモックモードで起動します: %s", exc)
            return _MockBackend(self.settings, self.on_coin_inserted)

    @property
    def is_mock(self):
        return isinstance(self._backend, _MockBackend)

    def simulate_coin_insert(self):
        """テスト用: ハードウェアなしでコイン投入イベントを発火する。"""
        self.on_coin_inserted()

    def dispense_capsule(self):
        self._backend.dispense_capsule()

    def close(self):
        self._backend.close()


class _MockBackend:
    def __init__(self, settings, on_coin_inserted):
        self.settings = settings
        self.on_coin_inserted = on_coin_inserted
        logger.info("モックモードで起動しました。実際のGPIOは操作されません。")

    def dispense_capsule(self):
        logger.info("[MOCK] サーボモーターを回転させてカプセルを排出します。")

    def close(self):
        pass


class _GpioBackend:
    def __init__(self, settings, on_coin_inserted):
        from gpiozero import Button, Servo

        self.settings = settings
        self.on_coin_inserted = on_coin_inserted

        bounce_time = settings.get("debounce_ms", 200) / 1000
        self.button = Button(settings["coin_pin"], bounce_time=bounce_time, pull_up=True)
        self.button.when_pressed = self._handle_coin

        self.servo = Servo(settings["servo_pin"])
        self._rest_value = self._angle_to_value(settings.get("servo_rest_angle", 0))
        self._dispense_value = self._angle_to_value(settings.get("servo_dispense_angle", 90))
        self.servo.value = self._rest_value

        logger.info("実機GPIOモードで起動しました(coin_pin=%s, servo_pin=%s)",
                    settings["coin_pin"], settings["servo_pin"])

    @staticmethod
    def _angle_to_value(angle_deg):
        # gpiozero の Servo.value は -1.0〜1.0 で 0〜180度に対応する
        return max(-1.0, min(1.0, (angle_deg / 90.0) - 1.0))

    def _handle_coin(self):
        self.on_coin_inserted()

    def dispense_capsule(self):
        self.servo.value = self._dispense_value
        time.sleep(self.settings.get("servo_hold_seconds", 1.0))
        self.servo.value = self._rest_value

    def close(self):
        self.button.close()
        self.servo.close()
