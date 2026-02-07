# Updated Singleton and Immortale Edition

class Singleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Singleton, cls).__new__(cls)
        return cls._instance

class Immortale(Singleton):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name


def run_app(executor):
    # Your application logic here that utilizes the executor
    print("App is running with executor:", executor)

# Example use
if __name__ == '__main__':
    executor = 'Executor Instance'
    run_app(executor)