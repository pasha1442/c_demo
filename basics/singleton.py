
class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        else:
            # because I wanted to initialise my class
            cls._instances[cls].__init__(*args, **kwargs)
        return cls._instances[cls]