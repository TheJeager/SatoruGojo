import logging


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    noisy = ["pyrogram", "httpx"]
    for name in noisy:
        logging.getLogger(name).setLevel(logging.WARNING)
