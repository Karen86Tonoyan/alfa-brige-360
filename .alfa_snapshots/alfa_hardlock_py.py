requested = req.profile if req.profile in MODELS else "balanced"
candidates = [requested] + [p for p in FALLBACK_CHAIN if p != requested]

messages = [
    {"role": "system", "content": req.system_prompt},
    {"role": "user", "content": req.prompt},
]

async def token_generator():
    nonlocal requested
    used_profile = None
    used_model = None

    async with httpx.AsyncClient(
        base_url=OLLAMA_BASE_URL,
        timeout=HTTP_TIMEOUT,
        transport=HTTP_TRANSPORT,
    ) as client:
        for p in candidates:
            cfg = MODELS[p]
            model_name = cfg["name"]
            payload = {
                "model": cfg["name"],
                "messages": messages,
                "options": {
                    "temperature": cfg["temperature"],
                    "top_p": cfg["top_p"],
                    "repeat_penalty": cfg["repeat_penalty"],
                    "num_predict": cfg["max_tokens"],
                },
                "stream": True,
            }

            try:
                logger.info(f"[STREAM] Profil [{p}] → Model [{model_name}]")
                async with client.stream("POST", "/api/chat", json=payload) as r:
                    r.raise_for_status()
                    used_profile = p
                    used_model = model_name

                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        # każdy chunk to JSON
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # Ollama /api/chat: {"message": {"role": "...", "content": "..."}, "done": bool}
                        msg = data.get("message", {})
                        delta = msg.get("content", "")
                        if delta:
                            yield delta
                    # jeśli doszliśmy tu bez wyjątku → zakończ
                    return
            except Exception as e:
                logger.warning(f"[STREAM] Model [{model_name}] padł ({e}) → fallback")
                continue

        # Jeśli wszystkie modele padły:
        yield "\n[ALFA_CRITICAL] Wszystkie modele offline."

return StreamingResponse(token_generator(), media_type="text/plain")