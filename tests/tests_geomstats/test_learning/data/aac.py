import geomstats.backend as gs
from geomstats.geometry.stratified.graph_space import (
    ExhaustiveAligner,
    GraphSpace,
    _GeodesicToPointAligner,
)
from geomstats.learning.aac import _AACGGPCA, _AACFrechetMean, _AACRegression
from geomstats.test.data import TestData
from geomstats.test.test_case import np_backend

IS_NOT_NP = not np_backend()


class AACTestData(TestData):
    skip_all = IS_NOT_NP

    def init_test_data(self):
        space_2 = GraphSpace(2, equip=True)
        metric = space_2.metric

        smoke_data = [
            dict(estimate="frechet_mean", metric=metric, expected_type=_AACFrechetMean),
            dict(estimate="ggpca", metric=metric, expected_type=_AACGGPCA),
            dict(estimate="regression", metric=metric, expected_type=_AACRegression),
        ]

        return self.generate_tests(smoke_data)


class _TrivialData:
    def __init__(self, Estimator, is_regression=False, n_samples=3):
        self.is_regression = is_regression
        self.Estimator = Estimator
        self.n_samples = n_samples

    def fit_warn_test_data(self):
        space_2 = GraphSpace(2, equip=True)
        space_2.metric.set_point_to_geodesic_aligner("default")

        X = space_2.random_point(self.n_samples)

        y = None
        if self.is_regression:
            y = X
            X = gs.expand_dims(gs.linspace(0, 1, num=self.n_samples), 1)

        return [dict(estimator=self.Estimator(space_2.metric), X=X, y=y)]


class _EstimatorTestData(TestData):
    def __init__(self):
        self.basic_data_generators = []
        self.data_generators = []
        self._setup()

    def _generate_test_data_from_generators(self, data_generators, func_name):
        smoke_data = []
        for data_generator in data_generators:
            smoke_data += getattr(data_generator, func_name)()

        return self.generate_tests(smoke_data)

    def fit_test_data(self):
        return self._generate_test_data_from_generators(
            self.data_generators, "fit_test_data"
        )

    def fit_warn_test_data(self):
        return self._generate_test_data_from_generators(
            self.basic_data_generators, "fit_warn_test_data"
        )


class _TrivialMeanData:
    def __init__(self, metrics, estimators, n_reps=2):
        self.metrics = metrics
        self.estimators = estimators
        self.n_reps = n_reps

    def fit_test_data(self):
        smoke_data = []
        for metric, estimator in zip(self.metrics, self.estimators):
            point = metric._space.random_point()
            points = gs.repeat(gs.expand_dims(point, 0), self.n_reps, axis=0)

            datum = dict(estimator=estimator, X=points, expected=point)
            smoke_data.append(datum)

        return smoke_data


class AACFrechetMeanTestData(_EstimatorTestData):
    skip_all = IS_NOT_NP

    def _setup(self):
        space_2 = GraphSpace(2)
        metric = space_2.metric
        metric.set_aligner(ExhaustiveAligner())

        metrics = [metric] * 2

        estimators = [_AACFrechetMean(metric) for metric in metrics]
        estimators[0].init_point = gs.zeros((2, 2))

        self.data_generators = [_TrivialMeanData(metrics, estimators, n_reps=2)]
        self.basic_data_generators = [_TrivialData(_AACFrechetMean)]

    def fit_id_niter_test_data(self):
        space_3 = GraphSpace(3)

        smoke_data = [
            dict(estimator=_AACFrechetMean(space_3.metric), X=space_3.random_point(4)),
        ]

        return self.generate_tests(smoke_data)


class _TrivialGeodesicData:
    def __init__(self, metrics, estimators, n_points=3):
        self.metrics = metrics
        self.estimators = estimators
        self.n_points = n_points

    def fit_test_data(self):
        smoke_data = []
        for metric, estimator in zip(self.metrics, self.estimators):
            init_point, end_point = metric._space.random_point(2)
            geo = metric.geodesic(init_point, end_point)

            s = gs.linspace(0.0, 1.0, self.n_points)
            points = geo(s)

            datum = dict(estimator=estimator, X=points)
            smoke_data.append(datum)

        return smoke_data


class AACGGPCATestData(_EstimatorTestData):
    skip_all = IS_NOT_NP

    tolerances = {
        "fit": {"atol": 1e-8},
    }

    def _setup(self):
        space_2 = GraphSpace(2)
        metric = space_2.metric

        metric.set_aligner(ExhaustiveAligner())

        aligner = _GeodesicToPointAligner()
        metric.set_point_to_geodesic_aligner(aligner)

        metrics = [metric] * 2
        estimators = [_AACGGPCA(metric) for metric in metrics]

        estimators[-1].init_point = gs.zeros((2, 2))

        self.data_generators = [_TrivialGeodesicData(metrics, estimators, n_points=3)]

        self.basic_data_generators = [_TrivialData(_AACGGPCA)]


class _TrivialRegressionData:
    def __init__(self, input_dim, metrics, estimators, n_samples=3):
        self.input_dim = input_dim
        self.metrics = metrics
        self.estimators = estimators
        self.n_samples = n_samples

    def fit_and_predict_test_data(self):
        smoke_data = []

        for p, metric, estimator in zip(self.input_dim, self.metrics, self.estimators):
            y = gs.repeat(
                gs.expand_dims(metric._space.random_point(), 0),
                self.n_samples,
                axis=0,
            )
            X = gs.repeat(
                gs.reshape(gs.linspace(0.0, 1.0, num=self.n_samples), (-1, 1)),
                p,
                axis=1,
            )
            datum = dict(estimator=estimator, X=X, y=y)
            smoke_data.append(datum)

        return smoke_data


class AACRegressionTestData(_EstimatorTestData):
    skip_all = IS_NOT_NP

    def _setup(self):
        space_2 = GraphSpace(2)
        metric = space_2.metric

        metric.set_aligner(ExhaustiveAligner())

        metric.set_point_to_geodesic_aligner(
            "default", s_min=-1.0, s_max=1.0, n_points=10
        )

        metrics = [metric] * 3
        estimators = [_AACRegression(metric) for metric in metrics]

        estimators[1].init_point = gs.zeros((2, 2))
        input_dim = [1, 1, 2]

        self.data_generators = [_TrivialRegressionData(input_dim, metrics, estimators)]

        self.basic_data_generators = [_TrivialData(_AACRegression, is_regression=True)]

    def fit_and_predict_test_data(self):
        return self._generate_test_data_from_generators(
            self.data_generators, "fit_and_predict_test_data"
        )
