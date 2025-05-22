# Author: Yiannis Charalambous

import types
import pytest
from esbmc_ai.singleton import SingletonMeta, makecls

class TestClass(metaclass=SingletonMeta):
    def __init__(self, value=None):
        self.value = value

@pytest.fixture(autouse=True)
def clear_singleton_instances():
    # Clear singleton instances before each test to ensure isolation
    SingletonMeta._instances.clear()

def test_single_instance():
    a = TestClass(10)
    b = TestClass(20)
    assert a is b, "Both variables should reference the same instance"

def test_initialization_only_once():
    a = TestClass(10)
    b = TestClass(20)
    assert a.value == 10
    assert b.value == 10

def test_state_persistence():
    a = TestClass(10)
    a.value = 42
    b = TestClass()
    assert b.value == 42

def test_different_singleton_classes():
    class AnotherClass(metaclass=SingletonMeta):
        pass
    a = TestClass()
    b = AnotherClass()
    assert a is not b, "Different singleton classes should not share the same instance"


# ============= Additional tests for makecls =====================

# A dummy metaclass to test conflict resolution
class CustomMeta(type):
    def __new__(mcs, name, bases, dct):
        dct['custom_attribute'] = 'custom'
        return super().__new__(mcs, name, bases, dct)

class BaseWithCustomMeta(metaclass=CustomMeta):
    pass

def test_makecls_conflict_resolution_priority_false():
    # Create a class that resolves metaclass conflicts without priority
    class ResolvedClass(BaseWithCustomMeta, metaclass=makecls(SingletonMeta)):
        pass

    instance1 = ResolvedClass()
    instance2 = ResolvedClass()
    
    assert instance1 is instance2, "Singleton behavior should be preserved"
    assert hasattr(instance1, 'custom_attribute'), "Custom attribute should exist from CustomMeta"
    assert instance1.custom_attribute == 'custom'

def test_makecls_conflict_resolution_priority_true():
    # Create a class that gives priority to SingletonMeta
    class ResolvedClass(BaseWithCustomMeta, metaclass=makecls(SingletonMeta, priority=True)):
        pass

    instance1 = ResolvedClass()
    instance2 = ResolvedClass()

    assert instance1 is instance2, "Singleton behavior should be preserved"
    assert hasattr(instance1, 'custom_attribute'), "Custom attribute should exist from CustomMeta"
    assert instance1.custom_attribute == 'custom'

def test_makecls_with_no_conflict():
    # Using makecls with only one metaclass and no inheritance
    class Simple(metaclass=makecls(SingletonMeta)):
        def __init__(self, data):
            self.data = data

    a = Simple(1)
    b = Simple(2)
    assert a is b
    assert b.data == 1

def test_makecls_different_classes_get_different_instances():
    # Classes with same meta setup should still produce different singleton instances
    class First(metaclass=makecls(SingletonMeta)):
        pass

    class Second(metaclass=makecls(SingletonMeta)):
        pass

    assert First() is not Second()
