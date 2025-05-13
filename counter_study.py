class Counter:
    def __init__(self, start=0):
        self.start = start
        self.value = start
    def inc(self, number=None):
        if number is None:
            self.value = self.value + 1
        else:
            self.value = self.value + number 
    def dec(self, number=None):
        if number is None:
            self.value = self.value - 1
        else:
            self.value = self.value - number 
        if self.value < 0:
            self.value = 0
class NonDecCounter(Counter):
    def dec(self, number=None):
        pass
class LimitedCounter(Counter):
    def __init__(self, start=0, limit=10):
        self.start = start
        self.limit = limit
        self.value = start
    def inc(self, number=None):
        if number is None:
            self.value = self.value + 1
        else:
            self.value = self.value + number 
        if self.value > self.limit:
            self.value = self.limit

counter = LimitedCounter()

print(counter.value)
counter.inc()
counter.inc(4)
print(counter.value)
counter.dec()
counter.dec(2)
print(counter.value)
counter.inc(20)
print(counter.value)
