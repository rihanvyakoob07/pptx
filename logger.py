import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(asctime)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%H:%M:%S; %Y-%m-%d',
)
logger = logging.getLogger(__name__)
logging.getLogger("openai").setLevel(logging.WARNING)