class TransactionFailed(Exception):
    """Raise to make a transaction fail and supports status code"""
    def __init__(self, message, status_code, *args):
        self.message = message
        self.status_code = status_code

        super(TransactionFailed, self).__init__(message, status_code, *args)
