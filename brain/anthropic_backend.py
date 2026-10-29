"""Backend Claude (API Anthropic). La chiave si legge da ANTHROPIC_API_KEY."""
from __future__ import annotations

import logging
import threading
from collections.abc import Iterator

from brain.base import Backend, BrainError
from i18n import t

log = logging.getLogger(__name__)


class AnthropicBackend(Backend):
    name = "anthropic"

    def __init__(self, cfg: dict) -> None:
        self.model = cfg["anthropic_model"]
        self.effort = cfg["anthropic_effort"]
        self.max_tokens = int(cfg["max_tokens"])
        self.timeout = float(cfg["timeout_s"])
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic  # import lento: lo facciamo solo al primo uso, nel thread
            # Le credenziali arrivano da ANTHROPIC_API_KEY (variabile d'ambiente)
            self._client = anthropic.Anthropic(timeout=self.timeout, max_retries=2)
        return self._client

    def stream_reply(self, system: str, messages: list[dict], cancel: threading.Event) -> Iterator[str]:
        import anthropic

        try:
            client = self._get_client()
            with client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=messages,
                output_config={"effort": self.effort},
            ) as stream:
                for text in stream.text_stream:
                    if cancel.is_set():
                        return
                    yield text
                final = stream.get_final_message()
        except anthropic.AuthenticationError:
            raise BrainError(t("claude_bad_key"))
        except anthropic.PermissionDeniedError:
            raise BrainError(t("claude_permission"))
        except anthropic.NotFoundError:
            raise BrainError(t("claude_model_missing", model=self.model))
        except anthropic.RateLimitError:
            raise BrainError(t("claude_rate_limited"))
        except anthropic.BadRequestError as e:
            log.error("Richiesta rifiutata: %s", e)
            raise BrainError(t("claude_bad_request"))
        except anthropic.APIStatusError as e:
            log.error("Errore API %s: %s", e.status_code, e)
            raise BrainError(t("claude_status", code=e.status_code))
        except anthropic.APITimeoutError:
            raise BrainError(t("claude_timeout"))
        except anthropic.APIConnectionError:
            raise BrainError(t("claude_connection"))
        except TypeError as e:
            # l'SDK solleva TypeError se non trova nessuna credenziale
            if "authentication" not in str(e).lower():
                raise
            raise BrainError(t("claude_no_key"))
        except anthropic.AnthropicError as e:
            # es. nessuna credenziale trovata
            log.error("Errore SDK Anthropic: %s", e)
            raise BrainError(t("claude_no_key"))

        log.info("Claude: stop_reason=%s, token in/out=%s/%s, request_id=%s", final.stop_reason,
                 final.usage.input_tokens, final.usage.output_tokens, getattr(final, "_request_id", None))
        if final.stop_reason == "refusal":
            raise BrainError(t("claude_refusal"))
        if final.stop_reason == "max_tokens":
            yield " …"
