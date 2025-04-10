import requests
import json
import os
import asyncio
import time
from app.models import ChatCompletionRequest, Message
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import httpx
import logging
import secrets
import string
from app.utils import format_log_message
from app.config.settings import (    
    RANDOM_STRING,
    RANDOM_STRING_LENGTH
)
from app.utils.logging import log

def generate_secure_random_string(length):
    all_characters = string.ascii_letters + string.digits
    secure_random_string = ''.join(secrets.choice(all_characters) for _ in range(length))
    return secure_random_string

logger = logging.getLogger('my_logger')

# 是否启用假流式请求 默认启用
FAKE_STREAMING = os.environ.get("FAKE_STREAMING", "true").lower() in ["true", "1", "yes"]
# 假流式请求的空内容返回间隔（秒）
FAKE_STREAMING_INTERVAL = float(os.environ.get("FAKE_STREAMING_INTERVAL", "1"))

@dataclass
class GeneratedText:
    text: str
    finish_reason: Optional[str] = None


class ResponseWrapper:
    def __init__(self, data: Dict[Any, Any]):  # 正确的初始化方法名
        self._data = data
        self._text = self._extract_text()
        self._finish_reason = self._extract_finish_reason()
        self._prompt_token_count = self._extract_prompt_token_count()
        self._candidates_token_count = self._extract_candidates_token_count()
        self._total_token_count = self._extract_total_token_count()
        self._thoughts = self._extract_thoughts()
        self._json_dumps = json.dumps(self._data, indent=4, ensure_ascii=False)

    def _extract_thoughts(self) -> Optional[str]:
        try:
            for part in self._data['candidates'][0]['content']['parts']:
                if 'thought' in part:
                    return part['text']
            return ""
        except (KeyError, IndexError):
            return ""

    def _extract_text(self) -> str:
        try:
            for part in self._data['candidates'][0]['content']['parts']:
                if 'thought' not in part:
                    return part['text']
            return ""
        except (KeyError, IndexError):
            return ""

    def _extract_finish_reason(self) -> Optional[str]:
        try:
            return self._data['candidates'][0].get('finishReason')
        except (KeyError, IndexError):
            return None

    def _extract_prompt_token_count(self) -> Optional[int]:
        try:
            return self._data['usageMetadata'].get('promptTokenCount')
        except (KeyError):
            return None

    def _extract_candidates_token_count(self) -> Optional[int]:
        try:
            return self._data['usageMetadata'].get('candidatesTokenCount')
        except (KeyError):
            return None

    def _extract_total_token_count(self) -> Optional[int]:
        try:
            return self._data['usageMetadata'].get('totalTokenCount')
        except (KeyError):
            return None

    @property
    def text(self) -> str:
        return self._text

    @property
    def finish_reason(self) -> Optional[str]:
        return self._finish_reason

    @property
    def prompt_token_count(self) -> Optional[int]:
        return self._prompt_token_count

    @property
    def candidates_token_count(self) -> Optional[int]:
        return self._candidates_token_count

    @property
    def total_token_count(self) -> Optional[int]:
        return self._total_token_count

    @property
    def thoughts(self) -> Optional[str]:
        return self._thoughts

    @property
    def json_dumps(self) -> str:
        return self._json_dumps


class GeminiClient:

    AVAILABLE_MODELS = []
    EXTRA_MODELS = os.environ.get("EXTRA_MODELS", "").split(",")

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def stream_chat(self, request: ChatCompletionRequest, contents, safety_settings, system_instruction):
        
        # 检查是否启用假流式请求
        if FAKE_STREAMING:
            extra_log={'key': self.api_key[:8], 'request_type': 'fake_stream', 'model': request.model}
            log('INFO', "使用假流式请求模式（发送换行符保持连接）", extra=extra_log)
            try:
                
                # 每隔一段时间发送换行符作为保活消息，直到外部取消此生成器
                start_time = time.time()
                while True:
                    yield "\n"
                    await asyncio.sleep(FAKE_STREAMING_INTERVAL)
                    
                    # 如果等待时间过长（超过300秒），抛出超时异常，让外部处理
                    if time.time() - start_time > 300:
                        log('ERROR', f"假流式请求等待时间过长",extra=extra_log)
                        
                        raise TimeoutError("假流式请求等待时间过长")
                
            except Exception as e:
                if not isinstance(e, asyncio.CancelledError):  
                    log('ERROR', f"假流式处理期间发生错误: {str(e)}", extra=extra_log)
                raise e
            finally:
                log('INFO', "假流式请求结束", extra=extra_log)
        else:
            # 真流式请求处理逻辑
            extra_log = {'key': self.api_key[:8], 'request_type': 'stream', 'model': request.model}
            log('INFO', "真流式请求开始", extra=extra_log)
            
            api_version = "v1alpha" if "think" in request.model else "v1beta"
            url = f"https://generativelanguage.googleapis.com/{api_version}/models/{request.model}:streamGenerateContent?key={self.api_key}&alt=sse"
            headers = {
                "Content-Type": "application/json",
            }
            data = {
                "contents": contents,
                "generationConfig": {
                    "temperature": request.temperature,
                    "maxOutputTokens": request.max_tokens,
                },
                "safetySettings": safety_settings,
            }
            if system_instruction:
                data["system_instruction"] = system_instruction
            
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, headers=headers, json=data, timeout=600) as response:
                    buffer = b""
                    try:
                        async for line in response.aiter_lines():
                            if not line.strip():
                                continue
                            if line.startswith("data: "):
                                line = line[len("data: "):]
                            buffer += line.encode('utf-8')
                            try:
                                data = json.loads(buffer.decode('utf-8'))
                                buffer = b""
                                if 'candidates' in data and data['candidates']:
                                    candidate = data['candidates'][0]
                                    if 'content' in candidate:
                                        content = candidate['content']
                                        if 'parts' in content and content['parts']:
                                            parts = content['parts']
                                            text = ""
                                            for part in parts:
                                                if 'text' in part:
                                                    text += part['text']
                                            if text:
                                                yield text
                                            
                                    if candidate.get("finishReason") and candidate.get("finishReason") != "STOP":
                                        error_msg = f"模型的响应被截断: {candidate.get('finishReason')}"
                                        extra_log_error = {'key': self.api_key[:8], 'request_type': 'stream', 'model': request.model, 'status_code': 'ERROR', 'error_message': error_msg}
                                        log_msg = format_log_message('WARNING', error_msg, extra=extra_log_error)
                                        logger.warning(log_msg)
                                        raise ValueError(error_msg)
                                    
                                    if 'safetyRatings' in candidate:
                                        for rating in candidate['safetyRatings']:
                                            if rating['probability'] == 'HIGH':
                                                error_msg = f"模型的响应被截断: {rating['category']}"
                                                extra_log_safety = {'key': self.api_key[:8], 'request_type': 'stream', 'model': request.model, 'status_code': 'ERROR', 'error_message': error_msg}
                                                log_msg = format_log_message('WARNING', error_msg, extra=extra_log_safety)
                                                logger.warning(log_msg)
                                                raise ValueError(error_msg)
                            except json.JSONDecodeError:
                                continue
                            except Exception as e:
                                error_msg = f"流式处理期间发生错误: {str(e)}"
                                extra_log_stream_error = {'key': self.api_key[:8], 'request_type': 'stream', 'model': request.model, 'status_code': 'ERROR', 'error_message': error_msg}
                                log_msg = format_log_message('ERROR', error_msg, extra=extra_log_stream_error)
                                logger.error(log_msg)
                                raise e
                    except Exception as e:
                        raise e
                    finally:
                        log_msg = format_log_message('INFO', "流式请求结束", extra=extra_log)
                        logger.info(log_msg)

    def complete_chat(self, request: ChatCompletionRequest, contents, safety_settings, system_instruction):
        extra_log = {'key': self.api_key[:8], 'request_type': 'non-stream', 'model': request.model, 'status_code': 'N/A'}
        log_msg = format_log_message('INFO', "非流式请求开始", extra=extra_log)
        logger.info(log_msg)
        
        api_version = "v1alpha" if "think" in request.model else "v1beta"
        url = f"https://generativelanguage.googleapis.com/{api_version}/models/{request.model}:generateContent?key={self.api_key}"
        headers = {
            "Content-Type": "application/json",
        }
        data = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
            "safetySettings": safety_settings,
        }
        if system_instruction:
            data["system_instruction"] = system_instruction
            
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            log_msg = format_log_message('INFO', "非流式请求成功完成", extra=extra_log)
            logger.info(log_msg)
            
            return ResponseWrapper(response.json())
        except Exception as e:
            raise

    def convert_messages(self, messages, use_system_prompt=False):
        gemini_history = []
        errors = []
        system_instruction_text = ""
        is_system_phase = use_system_prompt
        for i, message in enumerate(messages):
            role = message.role
            content = message.content
            if isinstance(content, str):
                if is_system_phase and role == 'system':
                    if system_instruction_text:
                        system_instruction_text += "\n" + content
                    else:
                        system_instruction_text = content
                else:
                    is_system_phase = False

                    if role in ['user', 'system']:
                        role_to_use = 'user'
                    elif role == 'assistant':
                        role_to_use = 'model'
                    else:
                        errors.append(f"Invalid role: {role}")
                        continue

                    if gemini_history and gemini_history[-1]['role'] == role_to_use:
                        gemini_history[-1]['parts'].append({"text": content})
                    else:
                        gemini_history.append(
                            {"role": role_to_use, "parts": [{"text": content}]})
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if item.get('type') == 'text':
                        parts.append({"text": item.get('text')})
                    elif item.get('type') == 'image_url':
                        image_data = item.get('image_url', {}).get('url', '')
                        if image_data.startswith('data:image/'):
                            try:
                                mime_type, base64_data = image_data.split(';')[0].split(':')[1], image_data.split(',')[1]
                                parts.append({
                                    "inline_data": {
                                        "mime_type": mime_type,
                                        "data": base64_data
                                    }
                                })
                            except (IndexError, ValueError):
                                errors.append(
                                    f"Invalid data URI for image: {image_data}")
                        else:
                            errors.append(
                                f"Invalid image URL format for item: {item}")

                if parts:
                    if role in ['user', 'system']:
                        role_to_use = 'user'
                    elif role == 'assistant':
                        role_to_use = 'model'
                    else:
                        errors.append(f"Invalid role: {role}")
                        continue
                    if gemini_history and gemini_history[-1]['role'] == role_to_use:
                        gemini_history[-1]['parts'].extend(parts)
                    else:
                        gemini_history.append(
                            {"role": role_to_use, "parts": parts})
        if errors:
            return errors
        else:
            if RANDOM_STRING:
                gemini_history.insert(1,{'role': 'user', 'parts': [{'text': generate_secure_random_string(RANDOM_STRING_LENGTH)}]})
                gemini_history.insert(len(gemini_history)-1,{'role': 'user', 'parts': [{'text': generate_secure_random_string(RANDOM_STRING_LENGTH)}]})
                log_msg = format_log_message('INFO', "伪装消息成功")
                logger.info(log_msg)
            return gemini_history, {"parts": [{"text": system_instruction_text}]}

    @staticmethod
    async def list_available_models(api_key) -> list:
        url = "https://generativelanguage.googleapis.com/v1beta/models?key={}".format(
            api_key)
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            models = [model["name"] for model in data.get("models", [])]
            models.extend(GeminiClient.EXTRA_MODELS)
            return models