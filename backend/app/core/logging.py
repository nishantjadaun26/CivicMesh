import logging


def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    # Do not log tokens, request bodies, precise locations, or signed media URLs.
