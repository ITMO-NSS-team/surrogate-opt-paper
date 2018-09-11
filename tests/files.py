import unittest

from src.evo_balt import Consts
from src.evo_balt.files import ForecastFile
from src.evo_balt.files import ObservationFile


class ObservationFileTest(unittest.TestCase):
    def test_time_series_correct(self):
        obs = ObservationFile("../samples/obs/1a_waves.txt")
        ts = obs.time_series(from_date=Consts.Models.Observations.timePeriodsStartTimes[Consts.State.currentPeriodId],
                             to_date=Consts.Models.Observations.timePeriodEndTimes[Consts.State.currentPeriodId])
        self.assertEqual(len(ts), 253)


class ForecastFileTest(unittest.TestCase):
    def test_time_series_correct(self):
        forecast = ForecastFile("../samples/results/K1.a")
        ts = forecast.time_series()
        self.assertEqual(len(ts), 4)