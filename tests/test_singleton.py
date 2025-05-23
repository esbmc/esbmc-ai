from typing import Dict, Optional, Tuple, Type, Any
import pytest
from esbmc_ai.singleton import (
    SingletonMeta,
    makecls,
)  # Assuming these exist in your environment


class MockClass(metaclass=SingletonMeta):
    def __init__(self, value: Optional[int] = None) -> None:
        self.value: Optional[int] = value


@pytest.fixture(autouse=True)
def clear_singleton_instances() -> None:
    # Clear singleton instances before each test to ensure isolation
    SingletonMeta._instances.clear()


def test_single_instance() -> None:
    a: MockClass = MockClass(10)
    b: MockClass = MockClass(20)
    assert a is b, "Both variables should reference the same instance"


def test_initialization_only_once() -> None:
    a: MockClass = MockClass(10)
    b: MockClass = MockClass(20)
    assert a.value == 10
    assert b.value == 10


def test_state_persistence() -> None:
    a: MockClass = MockClass(10)
    a.value = 42
    b: MockClass = MockClass()
    assert b.value == 42


def test_different_singleton_classes() -> None:
    class AnotherClass(metaclass=SingletonMeta):
        pass

    a: MockClass = MockClass()
    b: AnotherClass = AnotherClass()
    assert a is not b, "Different singleton classes should not share the same instance"


# ============= Additional tests for makecls =====================


class CustomMeta(type):
    def __new__(
        cls: Type["CustomMeta"],
        name: str,
        bases: Tuple[type, ...],
        namespace: Dict[str, Any],
    ) -> "CustomMeta":
        namespace["custom_attribute"] = "custom"
        return super().__new__(cls, name, bases, namespace)


class BaseWithCustomMeta(metaclass=CustomMeta):
    pass


def test_makecls_conflict_resolution_priority_false() -> None:
    class ResolvedClass(BaseWithCustomMeta, metaclass=makecls(SingletonMeta)):
        custom_attribute: str

    instance1: ResolvedClass = ResolvedClass()
    instance2: ResolvedClass = ResolvedClass()

    assert instance1 is instance2, "Singleton behavior should be preserved"
    assert hasattr(
        instance1, "custom_attribute"
    ), "Custom attribute should exist from CustomMeta"
    assert instance1.custom_attribute == "custom"


def test_makecls_conflict_resolution_priority_true() -> None:
    class ResolvedClass(
        BaseWithCustomMeta, metaclass=makecls(SingletonMeta, priority=True)
    ):
        custom_attribute: str

    instance1: ResolvedClass = ResolvedClass()
    instance2: ResolvedClass = ResolvedClass()

    assert instance1 is instance2, "Singleton behavior should be preserved"
    assert hasattr(
        instance1, "custom_attribute"
    ), "Custom attribute should exist from CustomMeta"
    assert instance1.custom_attribute == "custom"


def test_makecls_with_no_conflict() -> None:
    class Simple(metaclass=makecls(SingletonMeta)):
        def __init__(self, data: int) -> None:
            self.data: int = data

    a: Simple = Simple(1)
    b: Simple = Simple(2)
    assert a is b
    assert b.data == 1


def test_makecls_different_classes_get_different_instances() -> None:
    class First(metaclass=makecls(SingletonMeta)):
        pass

    class Second(metaclass=makecls(SingletonMeta)):
        pass

    assert First() is not Second()
