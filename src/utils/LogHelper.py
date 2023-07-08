import logging


class Logger:
    logger = None

    def __init__(self):
        pass

    @classmethod
    def get_level(cls, level):
        if level == "CRITICAL":
            return logging.CRITICAL
        elif level == "ERROR":
            return logging.ERROR
        elif level == "WARNING":
            return logging.WARNING
        elif level == "INFO":
            return logging.INFO
        elif level == "DEBUG":
            return logging.DEBUG
        else:
            return logging.NOTSET

    @classmethod
    def configure(cls, filelog=1, logfile="ma_cross_strategy.log", multilevel="DEBUG", consolelog=1,
                  _consoleloglevel="INFO"):
        # reduce informational logging
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

        # initialize class logger
        cls.logger = logging.getLogger('test_timeout')
        cls.logger.setLevel(logging.DEBUG)

        if not consolelog and not filelog:
            cls.logger.disabled = True

        if consolelog:
            # set a format which is simpler for console use
            console_handler_formatter = logging.Formatter('%(message)s')
            # define a Handler which writes sys.stdout
            console_handler = logging.StreamHandler()
            # Set log level
            console_handler.setLevel(cls.get_level(_consoleloglevel))

            # tell the handler to use this format
            console_handler.setFormatter(console_handler_formatter)
            # add the handler to the root logger
            cls.logger.addHandler(console_handler)

        if filelog:
            # set up logging to file
            file_handler_formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                                       datefmt='%Y-%m-%d %H:%M:%S')
            file_handler = logging.FileHandler(filename=logfile, mode='a')
            file_handler.setLevel(cls.get_level(multilevel))
            file_handler.setFormatter(file_handler_formatter)
            cls.logger.addHandler(file_handler)

    @classmethod
    def debug(cls, _str):
        cls.logger.debug(str)

    @classmethod
    def info(cls, _str):
        cls.logger.info(str)

    @classmethod
    def warning(cls, _str):
        cls.logger.warning(_str)

    @classmethod
    def error(cls, _str):
        cls.logger.error(_str)

    @classmethod
    def critical(cls, _str):
        cls.logger.critical(_str)
