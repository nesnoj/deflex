# -*- coding: utf-8 -*-

"""Adapting the general reegis power plants to the de21 model.

Copyright (c) 2016-2018 Uwe Krien <uwe.krien@rl-institut.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""
__copyright__ = "Uwe Krien <uwe.krien@rl-institut.de>"
__license__ = "GPLv3"


import pandas as pd
import os
import logging
import oemof.tools.logger as logger
import reegis_tools.geometries
import reegis_tools.config as cfg
import reegis_tools.powerplants
import de21.geometries


def add_model_region_pp(df):
    """Load the pp data set with geometries and add a column with the model
    region. Afterwards the geometry column is removed. As the renewable data
    set is big, the hdf5 format is used.
    """
    # Load de21 geometries
    de21_regions = de21.geometries.de21_regions()

    # Load power plant geometries
    pp = reegis_tools.geometries.Geometry(name='power plants', df=df)
    pp.create_geo_df()

    # Add region names to power plant table
    pp.gdf = reegis_tools.geometries.spatial_join_with_buffer(pp, de21_regions)
    df = pp.get_df()

    # Delete real geometries because they are not needed anymore.
    del df['geometry']

    logging.info("de21 regions added to power plant table.")
    return df


def pp_reegis2de21(clean_offshore=True):
    filename_in = os.path.join(cfg.get('paths', 'powerplants'),
                               cfg.get('powerplants', 'reegis_pp'))
    filename_out = os.path.join(cfg.get('paths', 'powerplants'),
                                cfg.get('powerplants', 'de21_pp'))
    if not os.path.isfile(filename_in):
        msg = "File '{0}' does not exist. Will create it from opsd file."
        logging.debug(msg.format(filename_in))
        filename_in = reegis_tools.powerplants.pp_opsd2reegis()
    pp = pd.read_hdf(filename_in, 'pp', mode='r')
    pp = add_model_region_pp(pp)
    pp = reegis_tools.powerplants.add_capacity_in(pp)

    # Remove PHES (storages)
    if cfg.get('powerplants', 'remove_phes'):
        pp = pp.loc[pp.technology != 'Pumped storage']

    # Remove powerplants outside Germany
    for state in cfg.get_list('powerplants', 'remove_states'):
        pp = pp.loc[pp.federal_states != state]

    if clean_offshore:
        pp = remove_onshore_technology_from_offshore_regions(pp)

    pp.to_hdf(filename_out, 'pp')
    return filename_out


def remove_onshore_technology_from_offshore_regions(df):
    logging.info("Removing onshore technology from offshore regions.")
    logging.info("The code is not efficient. So it may take a while.")

    dc = {'MV': 'DE01',
          'SH': 'DE13',
          'NI': 'DE14'}

    for ttype in ['Solar', 'Bioenergy', 'Wind']:
        for region in ['DE19', 'DE20', 'DE21']:
            logging.debug("Clean {1} from {0}.".format(region, ttype))

            c1 = df['energy_source_level_2'] == ttype
            c2 = df['de21_region'] == region

            condition = c1 & c2

            if ttype == 'Wind':
                condition = c1 & c2 & (df['technology'] == 'Onshore')

            for i, v in df.loc[condition].iterrows():
                df.loc[i, 'de21_region'] = (
                    dc[df.loc[i, 'federal_states']])
    return df


def get_de21_pp_by_year(year, overwrite_capacity=False):
    """

    Parameters
    ----------
    year : int
    overwrite_capacity : bool
        By default (False) a new column "capacity_<year>" is created. If set to
        True the old capacity column will be overwritten.

    Returns
    -------

    """
    filename = os.path.join(cfg.get('paths', 'powerplants'),
                            cfg.get('powerplants', 'de21_pp'))
    logging.info("Get de21 power plants for {0}.".format(year))
    if not os.path.isfile(filename):
        msg = "File '{0}' does not exist. Will create it from reegis file."
        logging.debug(msg.format(filename))
        filename = pp_reegis2de21()
    pp = pd.read_hdf(filename, 'pp', mode='r')

    filter_columns = ['capacity_{0}', 'capacity_in_{0}']

    # Get all powerplants for the given year.
    # If com_month exist the power plants will be considered month-wise.
    # Otherwise the commission/decommission within the given year is not
    # considered.
    print(pp.columns)
    for fcol in filter_columns:
        filter_column = fcol.format(year)
        orig_column = fcol[:-4]
        c1 = (pp['com_year'] < year) & (pp['decom_year'] > year)
        pp.loc[c1, filter_column] = pp.loc[c1, orig_column]

        c2 = pp['com_year'] == year
        pp.loc[c2, filter_column] = (pp.loc[c2, orig_column] *
                                     (12 - pp.loc[c2, 'com_month']) / 12)
        c3 = pp['decom_year'] == year
        pp.loc[c3, filter_column] = (pp.loc[c3, orig_column] *
                                     pp.loc[c3, 'com_month'] / 12)

        if overwrite_capacity:
            pp[orig_column] = 0
            pp[orig_column] = pp[filter_column]
            del pp[filter_column]

    return pp


if __name__ == "__main__":
    logger.define_logging()
    # pp_reegis2de21()
    my_df = get_de21_pp_by_year(2012, overwrite_capacity=False)
    logging.info('Done!')
    # exit(0)
    print(my_df[['capacity_2012', 'capacity_in_2012']].sum())
    print(my_df.groupby(['de21_region', 'energy_source_level_2']).sum()[[
        'capacity_2012', 'capacity_in_2012']])
    # print(my_df[['capacity', 'capacity_2012']].sum(axis=0))
