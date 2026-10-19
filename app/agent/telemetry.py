"""
LLM & Agent Telemetry: Latency, Token Usage and Cost Estimation Engine.
Tracks real-time performance and financial costs for local (Ollama) and cloud (Google Gemini) models.
"""
from typing import Dict, Any, Optional

# Pricing rates per 1,000,000 tokens (USD)
# Source: Google Cloud / AI Studio Official Pricing
MODEL_PRICING = {
    # Gemini 2.0 Flash
    "gemini-2.0-flash": {"input_per_m": 0.10, "output_per_m": 0.40},
    "gemini-2.0-flash-exp": {"input_per_m": 0.10, "output_per_m": 0.40},
    # Gemini 1.5 Flash
    "gemini-1.5-flash": {"input_per_m": 0.075, "output_per_m": 0.30},
    "gemini-1.5-flash-latest": {"input_per_m": 0.075, "output_per_m": 0.30},
    "gemini-flash-latest": {"input_per_m": 0.075, "output_per_m": 0.30},
    # Gemini 1.5 Pro
    "gemini-1.5-pro": {"input_per_m": 1.25, "output_per_m": 5.00},
    "gemini-1.5-pro-latest": {"input_per_m": 1.25, "output_per_m": 5.00},
    "gemini-pro-latest": {"input_per_m": 1.25, "output_per_m": 5.00},
}

def extract_token_usage(ai_response: Any) -> Dict[str, int]:
    """
    Trích xuất an toàn số lượng tokens (input, output, total) từ AIMessage.
    Hỗ trợ chuẩn LangChain usage_metadata lẫn response_metadata của Ollama và Gemini.
    """
    input_tokens = 0
    output_tokens = 0

    if hasattr(ai_response, "usage_metadata") and ai_response.usage_metadata:
        um = ai_response.usage_metadata
        input_tokens = um.get("input_tokens", 0)
        output_tokens = um.get("output_tokens", 0)
    elif hasattr(ai_response, "response_metadata") and ai_response.response_metadata:
        rm = ai_response.response_metadata
        # Ollama metadata
        if "prompt_eval_count" in rm or "eval_count" in rm:
            input_tokens = rm.get("prompt_eval_count", 0)
            output_tokens = rm.get("eval_count", 0)
        # Gemini usage_metadata nested
        elif "usage_metadata" in rm:
            gum = rm["usage_metadata"]
            input_tokens = gum.get("prompt_token_count", 0) or gum.get("input_tokens", 0)
            output_tokens = gum.get("candidates_token_count", 0) or gum.get("output_tokens", 0)

    total_tokens = input_tokens + output_tokens
    return {
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "total_tokens": int(total_tokens)
    }

def calculate_cost(model_name: str, input_tokens: int, output_tokens: int, provider: str = "gemini") -> float:
    """
    Tính toán chi phí USD dựa trên số token và model đã cấu hình.
    Với Ollama hoặc Rule-based fallback: Chi phí luôn bằng $0.00.
    """
    if provider.lower() in ["ollama", "local", "rule-based", "fallback"]:
        return 0.0

    model_key = model_name.lower().strip()
    rate = None
    for k, v in MODEL_PRICING.items():
        if k in model_key:
            rate = v
            break

    if rate is None:
        # Giá mặc định tương đương Gemini Flash
        rate = {"input_per_m": 0.10, "output_per_m": 0.40}

    cost = (input_tokens * rate["input_per_m"] + output_tokens * rate["output_per_m"]) / 1_000_000.0
    return round(cost, 6)

def format_telemetry_badge(metrics: Dict[str, Any]) -> str:
    """Định dạng chuỗi tóm tắt telemetry hiển thị trên log hoặc console."""
    lat_s = round(metrics.get("latency_ms", 0) / 1000.0, 2)
    tok = metrics.get("total_tokens", 0)
    cost = metrics.get("cost_usd", 0.0)
    model = metrics.get("model", "agent")
    
    cost_str = f"${cost:.5f}" if cost > 0 else "$0.00 (Local)"
    return f"⚡ {lat_s}s | 🪙 {tok} tokens | 💰 {cost_str} | 🤖 {model}"
