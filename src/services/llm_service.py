from typing import List, Dict, Optional
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from datetime import datetime, timedelta
from src.config import settings
from src.models.order import Order


class LLMService:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.generator = None
        self.device = settings.llm_device

    async def initialize(self):
        """Initialize the LLM model"""
        try:
            model_path = settings.llm_model_path
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None,
                low_cpu_mem_usage=True
            )

            if self.device == "cpu":
                self.model = self.model.to(self.device)

            self.generator = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if self.device == "cuda" else -1,
                max_new_tokens=settings.llm_max_tokens
            )
            print("LLM model loaded successfully")
        except Exception as e:
            print(f"Failed to load LLM model: {e}")
            # Fallback to simple text processing
            self.generator = None

    async def analyze_order_comment(self, comment: str) -> Dict[str, any]:
        """
        Анализировать комментарий к заказу для извлечения важной информации
        """
        if not comment or not self.generator:
            return {
                "priority": "normal",
                "special_instructions": [],
                "contact_preferences": "call_first",
                "estimated_prep_time": 0
            }

        prompt = f"""
        Проанализируй комментарий к заказу доставки и извлеки ключевую информацию:

        Комментарий: "{comment}"

        Верни ответ в формате JSON с полями:
        - priority: "high", "normal", "low" (срочность)
        - special_instructions: массив особых указаний
        - contact_preferences: "call_first", "no_call", "sms_ok"
        - estimated_prep_time: минуты на подготовку (число)

        JSON:
        """

        try:
            response = self.generator(prompt, max_new_tokens=200, temperature=0.1)
            generated_text = response[0]['generated_text']

            # Extract JSON from response
            json_start = generated_text.find('{')
            json_end = generated_text.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = generated_text[json_start:json_end]
                import json
                return json.loads(json_str)
        except Exception as e:
            print(f"LLM analysis error: {e}")

        # Fallback
        return {
            "priority": "normal",
            "special_instructions": [comment] if comment else [],
            "contact_preferences": "call_first",
            "estimated_prep_time": 0
        }

    async def generate_call_script(self, order: Order, estimated_delivery: datetime) -> str:
        """
        Сгенерировать скрипт звонка клиенту
        """
        if not self.generator:
            return self._simple_call_script(order, estimated_delivery)

        prompt = f"""
        Создай краткий скрипт звонка курьера клиенту для подтверждения доставки.

        Информация о заказе:
        - Адрес: {order.address}
        - Телефон: {order.phone}
        - Имя клиента: {order.customer_name or "клиент"}
        - Комментарий: {order.comment or "нет"}
        - Время доставки: {estimated_delivery.strftime('%H:%M')}

        Скрипт должен быть вежливым, кратким и содержать:
        1. Приветствие
        2. Подтверждение адреса и времени
        3. Вопрос о готовности принять заказ
        4. Прощание

        Скрипт на русском языке:
        """

        try:
            response = self.generator(prompt, max_new_tokens=300, temperature=0.3)
            return response[0]['generated_text'].strip()
        except Exception as e:
            print(f"Call script generation error: {e}")
            return self._simple_call_script(order, estimated_delivery)

    def _simple_call_script(self, order: Order, estimated_delivery: datetime) -> str:
        """Простой скрипт звонка без LLM"""
        customer_name = order.customer_name or "клиент"
        delivery_time = estimated_delivery.strftime('%H:%M')

        return f"""Здравствуйте, {customer_name}!
Это курьер, звоню по поводу вашего заказа.
Адрес доставки: {order.address}
Ориентировочное время прибытия: {delivery_time}
Заказ готов к доставке. Вы готовы принять заказ?
Спасибо за ожидание!"""

    async def calculate_call_time(self, order: Order, delivery_time: datetime) -> datetime:
        """
        Рассчитать оптимальное время звонка (минимум за 40 минут до доставки)
        """
        from src.config import settings

        # Analyze comment for special timing requirements
        if order.comment:
            analysis = await self.analyze_order_comment(order.comment)
            extra_prep_time = analysis.get("estimated_prep_time", 0)
        else:
            extra_prep_time = 0

        # Call at least 40 minutes before, plus any extra prep time
        call_advance = max(settings.call_advance_time, 40 + extra_prep_time)
        call_time = delivery_time - timedelta(minutes=call_advance)

        return call_time
