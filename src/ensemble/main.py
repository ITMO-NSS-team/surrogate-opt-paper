import csv
import datetime
import os
from functools import partial
from itertools import repeat
from multiprocessing import Pool

import numpy as np
from tqdm import tqdm

from src.ensemble.ensemble import Ensemble
from src.evolution.spea2 import SPEA2
from src.noice_experiments.errors import (
    error_rmse_all
)
from src.noice_experiments.evo_operators import (
    calculate_objectives_interp,
    crossover,
    mutation,
    initial_pop_lhs
)
from src.noice_experiments.model import (
    CSVGridFile,
    SWANParams,
    FakeModel
)
from src.utils.files import (
    wave_watch_results)
from src.utils.vis import (
    plot_results,
    plot_population_movement
)

ALL_STATIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9]


def model_all_stations():
    grid = CSVGridFile('../../samples/wind-exp-params-new.csv')
    ww3_obs = \
        [obs.time_series() for obs in
         wave_watch_results(path_to_results='../../samples/ww-res/', stations=ALL_STATIONS)]

    model = FakeModel(grid_file=grid, observations=ww3_obs, stations_to_out=ALL_STATIONS, error=error_rmse_all,
                      forecasts_path='../../../wind-noice-runs/results_fixed/0', noise_run=0)

    return model


def default_params_forecasts(model):
    '''
    Our baseline:  forecasts with default SWAN params
    '''

    closest_params = model.closest_params(params=SWANParams(drf=1.0,
                                                            cfw=0.015,
                                                            stpm=0.00302))
    default_params = SWANParams(drf=closest_params[0], cfw=closest_params[1], stpm=closest_params[2])
    drf_idx, cfw_idx, stpm_idx = model.params_idxs(default_params)
    forecasts = model.grid[drf_idx, cfw_idx, stpm_idx]

    return forecasts


def get_rmse_for_all_stations(forecasts, observations):
    # assert len(observations) == len(forecasts) == 3

    time = np.linspace(1, 253, num=len(forecasts[0].hsig_series))

    obs_series = []
    for obs in observations:
        obs_series.append(obs.time_series(from_date="20140814.120000", to_date="20140915.000000")[:len(time)])

    results_for_stations = np.zeros(len(forecasts))
    for idx in range(0, len(forecasts)):
        results_for_stations[idx] = np.sqrt(
            np.mean((np.array(forecasts[idx].hsig_series) - np.array(obs_series[idx])) ** 2))
    return results_for_stations


def optimize():
    grid = CSVGridFile('../../samples/wind-exp-params-new.csv')

    train_stations = [4, 5, 6]
    ww3_obs = \
        [obs.time_series() for obs in
         wave_watch_results(path_to_results='../../samples/ww-res/', stations=train_stations)]

    ens = Ensemble(grid=grid, noise_cases=[0, 1, 2, 15, 16, 17, 25, 26], observations=ww3_obs,
                   path_to_forecasts='../../../wind-noice-runs/results_fixed',
                   stations_to_out=train_stations, error=error_rmse_all)

    history, archive_history = SPEA2(
        params=SPEA2.Params(max_gens=150, pop_size=20, archive_size=5,
                            crossover_rate=0.8, mutation_rate=0.7, mutation_value_rate=[0.1, 0.001, 0.0005]),
        init_population=initial_pop_lhs,
        objectives=partial(calculate_objectives_interp, ens),
        crossover=crossover,
        mutation=mutation).solution()

    params = history.last().genotype

    test_model = model_all_stations()

    closest_hist = test_model.closest_params(params)
    closest_params_set_hist = SWANParams(drf=closest_hist[0], cfw=closest_hist[1], stpm=closest_hist[2])

    forecasts = []
    for row in grid.rows:
        if set(row.model_params.params_list()) == set(closest_params_set_hist.params_list()):
            drf_idx, cfw_idx, stpm_idx = test_model.params_idxs(row.model_params)
            forecasts = test_model.grid[drf_idx, cfw_idx, stpm_idx]
            break

    plot_results(forecasts=forecasts,
                 observations=wave_watch_results(path_to_results='../../samples/ww-res/', stations=ALL_STATIONS),
                 baseline=default_params_forecasts(test_model))
    plot_population_movement(archive_history, grid)

    return history


def run_robustess_exp_ens(max_gens, pop_size, archive_size, crossover_rate, mutation_rate, mutation_value_rate,
                          stations, **kwargs):
    grid = CSVGridFile('../../samples/wind-exp-params-new.csv')
    ww3_obs = \
        [obs.time_series() for obs in wave_watch_results(path_to_results='../../samples/ww-res/', stations=stations)]

    test_model = model_all_stations()
    default_forecasts = default_params_forecasts(test_model)

    ref_metrics = get_rmse_for_all_stations(default_forecasts,
                                            wave_watch_results(path_to_results='../../samples/ww-res/',
                                                               stations=ALL_STATIONS))

    train_model = Ensemble(grid=grid, noise_cases=[0, 1, 2, 15, 16, 17, 25, 26], observations=ww3_obs,
                           path_to_forecasts='../../../wind-noice-runs/results_fixed',
                           stations_to_out=stations, error=error_rmse_all)

    history, _ = SPEA2(
        params=SPEA2.Params(max_gens=max_gens, pop_size=pop_size, archive_size=archive_size,
                            crossover_rate=crossover_rate, mutation_rate=mutation_rate,
                            mutation_value_rate=mutation_value_rate),
        init_population=initial_pop_lhs,
        objectives=partial(calculate_objectives_interp, train_model),
        crossover=crossover,
        mutation=mutation).solution(verbose=False)

    params = history.last().genotype

    forecasts = []

    closest_hist = test_model.closest_params(params)
    closest_params_set_hist = SWANParams(drf=closest_hist[0], cfw=closest_hist[1], stpm=closest_hist[2])

    for row in grid.rows:
        if set(row.model_params.params_list()) == set(closest_params_set_hist.params_list()):
            drf_idx, cfw_idx, stpm_idx = test_model.params_idxs(row.model_params)
            forecasts = test_model.grid[drf_idx, cfw_idx, stpm_idx]
            break

    if 'save_figures' in kwargs and kwargs['save_figures'] is True:
        plot_results(forecasts=forecasts,
                     observations=wave_watch_results(path_to_results='../../samples/ww-res/', stations=ALL_STATIONS),
                     baseline=default_params_forecasts(test_model),
                     save=True, file_path=kwargs['figure_path'])

    metrics = get_rmse_for_all_stations(forecasts,
                                        wave_watch_results(path_to_results='../../samples/ww-res/',
                                                           stations=ALL_STATIONS))

    return [history.last(), metrics, ref_metrics]


objective_robustparams = {'a': 0, 'archive_size_rate': 0.3516265476722533, 'crossover_rate': 0.7194075160834003,
                          'max_gens': 3, 'mutation_p1': 0.18530572116666033, 'mutation_p2': 0.008275074614718868,
                          'mutation_p3': 0.000917588547202427, 'mutation_rate': 0.15718021655197123, 'pop_size': 19}

objective_q = {'a': 0, 'archive_size_rate': 0.18192329983957756, 'crossover_rate': 0.8275151161211388, 'max_gens': 4,
               'mutation_p1': 0.22471644990516082, 'mutation_p2': 0.004027729364749993,
               'mutation_p3': 0.000297583624177003, 'mutation_rate': 0.22663581900044313, 'pop_size': 9}

objective_tradeoff = {'a': 0, 'archive_size_rate': 0.35157832568915776, 'crossover_rate': 0.37407732045418357,
                      'max_gens': 9, 'mutation_p1': 0.21674397143802346, 'mutation_p2': 0.017216450597376923,
                      'mutation_p3': 0.0008306686136608031, 'mutation_rate': 0.2696660952766096, 'pop_size': 17}

objective_manual = {'a': 0, 'archive_size_rate': 0.3, 'crossover_rate': 0.3,
                    'max_gens': 30, 'mutation_p1': 0.1, 'mutation_p2': 0.01,
                    'mutation_p3': 0.001, 'mutation_rate': 0.5, 'pop_size': 20}

params_for_luck = {'a': 0, 'max_gens': 100, 'pop_size': 20,
                   'archive_size_rate': 0.25, 'crossover_rate': 0.8, 'mutation_rate': 0.7,
                   'mutation_p1': 0.1, 'mutation_p2': 0.001, 'mutation_p3': 0.0005
                   }


def robustness_statistics():
    param_for_run = params_for_luck

    stations_for_run_set2 = [[1],
                             [1, 2],
                             [1, 2, 3],
                             [1, 2, 3, 4],
                             [1, 2, 3, 4, 5],
                             [1, 2, 3, 4, 5, 6],
                             [4],
                             [4, 5],
                             [4, 5, 6],
                             [4, 5, 6, 7],
                             [4, 5, 6, 7, 8],
                             [4, 5, 6, 7, 8, 9],
                             [1],
                             [1, 2],
                             [1, 3, 3],
                             [1, 1, 3, 7],
                             [1, 2, 3, 7, 8],
                             [1, 2, 3, 7, 8, 9]]
    stations_metrics = np.zeros(9)

    exptime = str(datetime.datetime.now().time()).replace(":", "-")
    os.mkdir(f'../../{exptime}')

    with open(f'../exp-res-ens-{exptime}.csv', 'w', newline='') as csvfile:
        fieldnames = ['ID', 'IterId', 'SetId', 'drf', 'cfw', 'stpm',
                      'st1', 'st2', 'st3', 'st4', 'st5', 'st6', 'st7', 'st8', 'st9']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()

    cpu_count = 8

    for iteration in range(10):
        results = []
        with Pool(processes=cpu_count) as p:
            runs_total = len(stations_for_run_set2)
            fig_paths = [os.path.join('../..', exptime, str(iteration * runs_total + run)) for run in range(runs_total)]
            all_packed_params = []
            for station, params, fig_path in zip(stations_for_run_set2, repeat(param_for_run), fig_paths):
                all_packed_params.append([station, params, fig_path])

            with tqdm(total=runs_total) as progress_bar:
                for _, out in tqdm(enumerate(p.imap_unordered(robustness_run, all_packed_params))):
                    results.append(out)
                    progress_bar.update()

        for idx, out in enumerate(results):
            best, metrics, ref_metrics = out

            stations_metrics[0:9] = metrics / ref_metrics

            with open(f'../exp-res-ens-{exptime}.csv', 'a', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                row_to_write = {'ID': iteration * runs_total + idx, 'IterId': iteration, 'SetId': idx,
                                'drf': best.genotype.drf,
                                'cfw': best.genotype.cfw,
                                'stpm': best.genotype.stpm}
                for station_idx in range(len(metrics)):
                    key = f'st{station_idx + 1}'
                    row_to_write.update({key: stations_metrics[station_idx]})
                writer.writerow(row_to_write)


def robustness_run(packed_args):
    stations_for_run, param_for_run, figure_path = packed_args
    archive_size = round(param_for_run['archive_size_rate'] * param_for_run['pop_size'])
    mutation_value_rate = [param_for_run['mutation_p1'], param_for_run['mutation_p2'],
                           param_for_run['mutation_p3']]
    best, metrics, ref_metrics = run_robustess_exp_ens(max_gens=param_for_run['max_gens'],
                                                       pop_size=param_for_run['pop_size'],
                                                       archive_size=archive_size,
                                                       crossover_rate=param_for_run['crossover_rate'],
                                                       mutation_rate=param_for_run['mutation_rate'],
                                                       mutation_value_rate=mutation_value_rate,
                                                       stations=stations_for_run,
                                                       save_figures=True,
                                                       figure_path=figure_path)

    return best, metrics, ref_metrics


#
# optimize()


if __name__ == '__main__':
    robustness_statistics()