import csv
import os
import random
from collections import Counter
from math import sqrt

import numpy as np

from src.noice_experiments.noisy_wind_files import (
    files_by_stations,
    forecast_files_from_dir,
    extracted_forecast_params
)
from src.swan.files import (
    ForecastFile,
    ObservationFile
)

cfw_range = [0.005, 0.01, 0.015, 0.02, 0.025, 0.030000000000000002, 0.035, 0.04, 0.045, 0.049999999999999996]
stpm_range = [0.001, 0.002, 0.003, 0.004]


class SWANParams:

    @staticmethod
    def new_instance():
        return SWANParams(drf=random.uniform(0, 5), cfw=random.choice(cfw_range), stpm=random.choice(stpm_range))

    def __init__(self, drf, cfw, stpm):
        self.drf = drf
        self.cfw = cfw
        self.stpm = stpm

    def update(self, drf, cfw, stpm):
        self.drf = drf
        self.cfw = cfw
        self.stpm = stpm

    def params_list(self):
        return [self.drf, self.cfw, self.stpm]


class FakeModel:
    def __init__(self, grid_file, forecasts_path, noise_run=1):
        self.grid_file = grid_file
        self.observations = observations_from_files()
        self.forecasts_path = forecasts_path
        self.noise_run = noise_run
        self._init_grids()

    def _init_grids(self):
        self.grid = self._empty_grid()

        files = forecast_files_from_dir(self.forecasts_path)

        stations = files_by_stations(files, noise_run=self.noise_run)

        files_by_run_idx = dict()

        for station in stations:
            for file in station:
                _, name = os.path.split(file)
                _, _, run_idx = extracted_forecast_params(file_name=name)

                files_by_run_idx[file] = run_idx

        for row in self.grid_file.rows:
            run_idx = row.id
            forecasts_files = sorted([key for key in files_by_run_idx.keys() if files_by_run_idx[key] == run_idx])

            forecasts = []
            for station_idx, file_name in enumerate(forecasts_files):
                forecasts.append(FakeModel.Forecast(station_idx, ForecastFile(path=file_name)))

            drf_idx, cfw_idx, stpm_idx = self.params_idxs(row.model_params)
            self.grid[drf_idx, cfw_idx, stpm_idx] = forecasts

    def _empty_grid(self):
        return np.empty((len(self.grid_file.drf_grid),
                         len(self.grid_file.cfw_grid),
                         len(self.grid_file.stpm_grid)),
                        dtype=list)

    def params_idxs(self, params):
        drf_idx = self.grid_file.drf_grid.index(params.drf)
        cfw_idx = self.grid_file.cfw_grid.index(params.cfw)
        stpm_idx = self.grid_file.stpm_grid.index(params.stpm)

        return drf_idx, cfw_idx, stpm_idx

    def closest_params(self, params):
        drf = min(self.grid_file.drf_grid, key=lambda val: abs(val - params.drf))
        cfw = min(self.grid_file.cfw_grid, key=lambda val: abs(val - params.cfw))
        stpm = min(self.grid_file.stpm_grid, key=lambda val: abs(val - params.stpm))

        return drf, cfw, stpm

    def output(self, params):
        drf_idx, cfw_idx, stpm_idx = self.params_idxs(params=params)
        return [self.error(forecast) for forecast in self.grid[drf_idx, cfw_idx, stpm_idx]]

    def error(self, forecast):
        '''
        Calculate RMSE of between forecasts and observations for corresponding station
        :param forecast: Forecast object
        '''

        observation = self.observations[forecast.station_idx]

        result = 0.0
        for pred, obs in zip(forecast.hsig_series, observation):
            result += pow(pred - obs, 2)

        return sqrt(result / len(observation))

    class Forecast:
        def __init__(self, station_idx, forecast_file):
            self.station_idx = station_idx
            self.file = forecast_file

            self.hsig_series = self._station_series()

        def _station_series(self):
            hsig_idx = 1
            return [float(line.split()[hsig_idx]) for line in self.file.time_series()]


class CSVGridFile:
    def __init__(self, path):
        self.path = path
        self._load()

    def _load(self):
        with open(os.path.join(os.path.dirname(__file__), self.path), newline='') as csvfile:
            reader = csv.DictReader(csvfile)

            self.rows = [CSVGridRow(row) for row in reader]

            drf_values = [row.model_params.drf for row in self.rows]
            cfw_values = [row.model_params.cfw for row in self.rows]
            stpm_values = [row.model_params.stpm for row in self.rows]

            self.drf_grid = unique_values(drf_values)
            self.cfw_grid = unique_values(cfw_values)
            self.stpm_grid = unique_values(stpm_values)

            print(self.drf_grid)
            print(self.cfw_grid)
            print(self.stpm_grid)


class CSVGridRow:
    def __init__(self, row):
        self.id = row['ID']
        self.model_params = self._swan_params(row)

    @classmethod
    def _swan_params(cls, csv_row):
        return SWANParams(drf=float(csv_row['DRF']), cfw=float(csv_row['CFW']), stpm=float(csv_row['STPM']))


def unique_values(values):
    cnt = Counter(values)
    return list(cnt.keys())


def observations_from_files():
    return [ObservationFile(path="../../samples/obs/1a_waves.txt").time_series(from_date="20140814.120000",
                                                                               to_date="20140915.000000"),
            ObservationFile(path="../../samples/obs/2a_waves.txt").time_series(from_date="20140814.120000",
                                                                               to_date="20140915.000000"),
            ObservationFile(path="../../samples/obs/3a_waves.txt").time_series(from_date="20140814.120000",
                                                                               to_date="20140915.000000")
            ]
