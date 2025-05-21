from abc import ABC, abstractmethod


def average(iterable):
    return sum(iterable) / len(iterable)

class Stat(ABC):
    def __init__(self, iterable=[]):
        self.iterable  = list(iterable)

    def add(self, number):
        self.iterable.append(number)

    @abstractmethod
    def result(self):
        pass
   
    def clear(self):
        self.iterable = []
  
class MinStat(Stat):
    def result(self):
        if self.iterable == []:
            return None
        else:
            return min(self.iterable)

class MaxStat(Stat):
    def result(self):
        if self.iterable == []:
            return None
        else:
            return max(self.iterable)
        
class AverageStat (Stat):
    def result(self):
        if self.iterable == []:
            return None
        else:
            return average(self.iterable)
