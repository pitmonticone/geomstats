"""Pytest utility classes, functions and fixtures."""

import inspect
import os
import types

import numpy as np
import pytest

import geomstats.backend as gs


def autograd_backend():
    """Check if autograd is set as backend."""
    return os.environ["GEOMSTATS_BACKEND"] == "autograd"


def np_backend():
    """Check if numpy is set as backend."""
    return os.environ["GEOMSTATS_BACKEND"] == "numpy"


def pytorch_backend():
    """Check if pytorch is set as backend."""
    return os.environ["GEOMSTATS_BACKEND"] == "pytorch"


def tf_backend():
    """Check if tensorflow is set as backend."""
    return os.environ["GEOMSTATS_BACKEND"] == "tensorflow"


if tf_backend():
    import tensorflow as tf

    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

if pytorch_backend():
    import torch


autograd_only = pytest.mark.skipif(
    not autograd_backend(), reason="Test for autograd backend only."
)
np_only = pytest.mark.skipif(not np_backend(), reason="Test for numpy backend only.")
torch_only = pytest.mark.skipif(
    not pytorch_backend(), reason="Test for pytorch backends only."
)
tf_only = pytest.mark.skipif(
    not tf_backend(), reason="Test for tensorflow backends only."
)

np_and_tf_only = pytest.mark.skipif(
    not (np_backend() or tf_backend()),
    reason="Test for numpy and tensorflow backends only.",
)
np_and_torch_only = pytest.mark.skipif(
    not (np_backend() or pytorch_backend()),
    reason="Test for numpy and pytorch backends only.",
)
np_and_autograd_only = pytest.mark.skipif(
    not (np_backend() or autograd_backend()),
    reason="Test for numpy and autograd backends only.",
)
autograd_and_torch_only = pytest.mark.skipif(
    not (autograd_backend() or pytorch_backend()),
    reason="Test for autograd and torch backends only.",
)
autograd_and_tf_only = pytest.mark.skipif(
    not (autograd_backend() or tf_backend()),
    reason="Test for autograd and tf backends only.",
)

np_autograd_and_tf_only = pytest.mark.skipif(
    not (np_backend() or autograd_backend() or tf_backend()),
    reason="Test for numpy, autograd and tensorflow backends only.",
)
np_autograd_and_torch_only = pytest.mark.skipif(
    not (np_backend() or autograd_backend() or pytorch_backend()),
    reason="Test for numpy, autograd and pytorch backends only.",
)
autograd_tf_and_torch_only = pytest.mark.skipif(
    np_backend(), reason="Test for backends with automatic differentiation only."
)


def pytorch_error_msg(a, b, rtol, atol):
    msg = f"\ntensor 1\n{a}\ntensor 2\n{b}"
    if torch.is_tensor(a) and torch.is_tensor(b):
        if a.dtype == torch.bool and b.dtype == torch.bool:
            diff = torch.logical_xor(a, b)
            msg = msg + f"\ndifference \n{diff}"
        else:
            diff = torch.abs(a - b)
            msg = msg + f"\ndifference \n{diff}\nrtol {rtol}\natol {atol}"
    return msg


def copy_func(f, name=None):
    """
    Return a function with same code, globals, defaults, closure, and
    name (or provide a new name)
    """
    fn = types.FunctionType(
        f.__code__, f.__globals__, name or f.__name__, f.__defaults__, f.__closure__
    )
    fn.__dict__.update(f.__dict__)
    return fn


class Parametrizer(type):
    """Metaclass for test classes.

    Note: A test class is a class that inherits from TestCase.
    For example, `class TestEuclidean(TestCase)` defines
    a test class.

    The Parametrizer helps its test class by pairing:
    - the different test functions of the test class:
      - e.g. the test function `test_belongs`,
    - with different test data, generated by auxiliary test data functions
      - e.g. the test data function `belongs_data` that generates data
      to test the function `belongs`.

    As such, Parametrizer acts as a "metaclass" of its test class:
    `class TestEuclidean(TestCase, metaclass=Parametrizer)`.

    Specifically, Parametrizer decorates every test function inside
    its test class with pytest.mark.parametrizer, with the exception
    of the test class' class methods and static methods.

    Two conventions need to be respected:
    1. The test class should contain an attribute named 'testing_data'.
      - `testing_data` is an object inheriting from `TestData`.
    2. Every test function should have its corresponding test data function created
    inside the TestData object called `testing_data`.

    A sample test class looks like this:

    ```
    class TestEuclidean(TestCase, metaclass=Parametrizer):
        class TestDataEuclidean(TestData):
            def belongs_data():
                ...
                return self.generate_tests(...)
        testing_data = TestDataEuclidean()
        def test_belongs():
            ...
    ```
    Parameters
    ----------
    cls : child class of TestCase
        Test class, i.e. a class inheriting from TestCase
    name : str
        Name of the test class
    bases : TestCase
        Parent class of the test class: TestCase.
    attrs : dict
        Attributes of the test class, for example its methods,
        stored in a dictionnary as (key, value) when key gives the
        name of the attribute (for example the name of the method),
        and value gives the actual attribute (for example the method
        itself.)

    References
    ----------
    More on pytest's parametrizers can be found here:
    https://docs.pytest.org/en/6.2.x/parametrize.html
    """

    def __new__(cls, name, bases, attrs):
        """Decorate the test class' methods with pytest."""
        for base in bases:
            test_fn_list = [fn for fn in dir(base) if fn.startswith("test")]
            for test_fn in test_fn_list:
                attrs[test_fn] = copy_func(getattr(base, test_fn))

        skip_all = attrs.get("skip_all", False)

        testing_data = locals()["attrs"].get("testing_data", None)
        if testing_data is None:
            raise Exception(
                "Testing class doesn't have class object" " named 'testing_data'"
            )
        cls_tols = (
            testing_data.tolerances if hasattr(testing_data, "tolerances") else {}
        )

        for attr_name, attr_value in attrs.copy().items():
            if isinstance(attr_value, types.FunctionType):

                if (
                    not skip_all
                    and ("skip_" + attr_name, True) not in locals()["attrs"].items()
                ):
                    arg_names = inspect.getfullargspec(attr_value)[0]
                    args_str = ", ".join(arg_names[1:])
                    data_fn_str = attr_name[5:] + "_test_data"

                    if not hasattr(testing_data, data_fn_str):
                        raise Exception(
                            "testing_data object doesn't have '{}' function for "
                            "pairing with '{}'".format(data_fn_str, attr_name)
                        )
                    test_data = getattr(testing_data, data_fn_str)()
                    if test_data is None:
                        raise Exception(
                            "'{}' returned None. should be list".format(data_fn_str)
                        )

                    test_data = _dictify_test_data(test_data, arg_names[1:])
                    test_data = _handle_tolerances(
                        attr_name[5:],
                        arg_names[1:],
                        test_data,
                        cls_tols,
                    )
                    test_data = _pytestify_test_data(
                        attr_name, test_data, arg_names[1:]
                    )

                    attrs[attr_name] = pytest.mark.parametrize(
                        args_str,
                        test_data,
                    )(attr_value)
                else:
                    attrs[attr_name] = pytest.mark.skip("skipped")(attr_value)

        return super(Parametrizer, cls).__new__(cls, name, bases, attrs)


class TestCase:
    """Class for Geomstats tests."""

    def assertAllClose(self, a, b, rtol=gs.rtol, atol=gs.atol):
        if tf_backend():
            return tf.test.TestCase().assertAllClose(a, b, rtol=rtol, atol=atol)
        if np_backend() or autograd_backend():
            return np.testing.assert_allclose(a, b, rtol=rtol, atol=atol)

        return self.assertTrue(
            gs.allclose(a, b, rtol=rtol, atol=atol),
            msg=pytorch_error_msg(a, b, rtol, atol),
        )

    def assertAllEqual(self, a, b):
        if tf_backend():
            return tf.test.TestCase().assertAllEqual(a, b)

        elif np_backend() or autograd_backend():
            np.testing.assert_array_equal(a, b)

        else:
            self.assertTrue(gs.equal(a, b))

    def assertTrue(self, condition, msg=None):
        assert condition, msg

    def assertFalse(self, condition, msg=None):
        assert not condition, msg

    def assertEqual(self, a, b):
        assert a == b

    def assertAllCloseToNp(self, a, np_a, rtol=gs.rtol, atol=gs.atol):
        are_same_shape = np.all(a.shape == np_a.shape)
        are_same = np.allclose(a, np_a, rtol=rtol, atol=atol)
        assert are_same and are_same_shape

    def assertShapeEqual(self, a, b):
        if tf_backend():
            return tf.test.TestCase().assertShapeEqual(a, b)
        assert a.shape == b.shape


def _dictify_test_data(test_data, arg_names):

    tests = []
    for test_datum in test_data:
        if not isinstance(test_datum, dict):
            marks = test_datum[-1]
            test_datum = {
                name: value for name, value in zip(arg_names, test_datum[:-1])
            }
            test_datum["marks"] = marks

        tests.append(test_datum)

    return tests


def _handle_tolerances(func_name, arg_names, test_data, cls_tols):

    has_tol = False
    for arg_name in arg_names:
        if arg_name.endswith("tol"):
            has_tol = True
            break

    if not has_tol:
        return test_data

    func_tols = cls_tols.get(func_name, {})

    tols = dict()
    for arg_name in arg_names:
        if arg_name.endswith("rtol"):
            tols[arg_name] = func_tols.get(arg_name, gs.rtol)
        elif arg_name.endswith("tol"):
            tols[arg_name] = func_tols.get(arg_name, gs.atol)

    for test_datum in test_data:
        for tol_arg_name, tol in tols.items():
            test_datum.setdefault(tol_arg_name, tol)

    return test_data


def _pytestify_test_data(func_name, test_data, arg_names):

    tests = []
    for test_datum in test_data:
        try:
            values = [test_datum[key] for key in arg_names]
        except KeyError:
            raise Exception(
                f"{func_name} requires the following arguments: "
                f"{', '.join(arg_names)}"
            )
        tests.append(pytest.param(*values, marks=pytest.mark.random))

    return tests
