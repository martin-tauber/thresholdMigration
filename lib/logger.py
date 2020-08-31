import logging

#-----------------------
# Logger
#-----------------------
class LoggerFactory():
    def __init__(self):
        pass

    def getLogger(self, name):
        logger = logging.getLogger(name)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logger.setLevel(logging.DEBUG)

        return logger

LoggerFactory = LoggerFactory()