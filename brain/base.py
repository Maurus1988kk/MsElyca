"""Interfaccia comune dei backend LLM.

Per aggiungere un nuovo modello/servizio: crea brain/<nome>_backend.py con una sottoclasse
di Backend e registrala in make_backend() (brain/__init__.py).
"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator


class BrainError(Exception):
    """Errore da mostrare all'utente nel fumetto (messaggio già tradotto)."""


class Backend(ABC):
    name = "base"
    # impostato da Brain: mostra un messaggio di stato nel fumetto (es. download del modello)
    status_callback: Callable[[str], None] | None = None

    def report_status(self, message: str) -> None:
        if self.status_callback is not None:
            self.status_callback(message)

    @abstractmethod
    def stream_reply(self, system: str, messages: list[dict], cancel: threading.Event) -> Iterator[str]:
        """Genera la risposta a pezzi di testo.

        `messages` è la cronologia [{"role": "user"|"assistant", "content": str}, ...]
        che termina con la domanda dell'utente. Deve fermarsi presto se `cancel` è
        impostato. In caso di problemi solleva BrainError con un messaggio leggibile.
        """
