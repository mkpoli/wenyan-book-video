import sys
import threading
import time
import itertools
from typing import Optional, ContextManager

class Spinner(ContextManager['Spinner']):
    def __init__(self, message: str = "Processing...", delay: float = 0.1):
        self.message = message
        self.delay = delay
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None

    def __enter__(self) -> 'Spinner':
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        if exc_type is None:
            # clear the line on success
            sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
            sys.stdout.flush()
        else:
            # leave the line on failure for context
            sys.stdout.write("\n")
            sys.stdout.flush()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()

    def stop(self):
        if self.thread and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join()

    def update(self, message: str):
        self.message = message

    def _spin(self):
        spinner = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])
        while not self.stop_event.is_set():
            sys.stdout.write("\r" + next(spinner) + " " + self.message)
            sys.stdout.flush()
            # Wait for specific interval, but check stop_event frequently
            # to remain responsive
            for _ in range(int(self.delay * 100)):
                if self.stop_event.is_set():
                    return
                time.sleep(0.01)
