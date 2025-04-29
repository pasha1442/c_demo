

class Singleton:
    # This method is called when decorator wraps given class
    # cls is the decorated class
    def __init__(self, cls):
        self.cls = cls
        self.instance = None

    # This method is called every time when decorated class is called as function i.e. when creating instance
    # we check if we already have instance for decorated class, return that in that case,
    # otherwise create a new instance, save it and return
    def __call__(self, *args, **kwargs):
        if self.instance is None:
            self.instance = self.cls(*args, **kwargs)
        return self.instance