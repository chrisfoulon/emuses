optim_dict_default = {
    'param': {
        'umap': {
            'min_dist': {'name': 'min_dist', 'low': 0.01, 'high': 0.5},
            'n_neighbors': {'name': 'n_neighbors', 'low': 5, 'high': 50, 'step': 5},
            'n_components': {'value': 2},
            'metric': {'name': 'metric', 'choices': ['euclidean']}
        },
        'hdbscan': {
            'min_cluster_size': {'name': 'min_cluster_size', 'low': 5, 'high': 50},
            'min_samples': {'name': 'min_samples', 'low': 1, 'high': 10}
        }
    },
    'metrics': {
        'umap': {
            'spread': {
                'weight': 1.0,       # Slightly reduced if you want clusters to be tighter.
                'target': 0.2,
                'epsilon': 0.05
            },
            'density_variability': {
                'weight': 1.5,
                'target': 0.4,
                'epsilon': 0.05
            },
            'entropy': {
                'weight': 1.2,       # Increase the weight on entropy to drive down uniformity.
                'target': 0.3,       # Target lower entropy to encourage well-defined subregions.
                'epsilon': 0.1
            }
        },
        'hdbscan': {
            'cluster_persistence': {
                'weight': 1.0
            },
            'noise_ratio': {
                'weight': 1.0,
                'target': 0.9,       # Ensuring a low noise level (e.g., 10% noise).
                'epsilon': 0.05
            },
            'validity_index': {
                'weight': 2.0        # High weight to ensure clusters are compact and well separated.
            }
        }
    }
}



optim_dict_test = {
    'param': {
        'umap': {
            'min_dist': {'name': 'min_dist', 'value': 0.39},
            'n_neighbors': {'name': 'n_neighbors', 'value': 50},
            'n_components': {'value': 2},
            'metric': {'name': 'metric', 'choices': ['euclidean']}
        },
        'hdbscan': {
            'min_cluster_size': {'name': 'min_cluster_size', 'low': 5, 'high': 50},
            'min_samples': {'name': 'min_samples', 'low': 1, 'high': 10}
        }
    },
    'metrics': {
        'umap': {
            'spread': {
                'weight': 1.5,
                'target': 0.6,
                'epsilon': 0.1
            },
            'density_variability': {
                'weight': 1.2,
                'target': 0.4,
                'epsilon': 0.1
            },
            'entropy': {
                'weight': 1.0
            }
        },
        'hdbscan': {
            # 'cluster_persistence': {
            #     'weight': 2.0
            # },
            'noise_ratio': {
                'weight': 1.0,
                'target': 0.1,
                'epsilon': 0.05
            },
            'validity_index': {
                'weight': 1.5
            }
        }
    }
}


optim_dict_mnist = {
    'param': {
        'umap': {
            'min_dist': {'name': 'min_dist', 'value': 0.08393266179885042},
            'n_neighbors': {'name': 'n_neighbors', 'value': 5},
            'n_components': {'name': 'n_components', 'value': 2},
            'metric': {'name': 'metric', 'choices': ['euclidean']}
        },
        'hdbscan': {
            'min_cluster_size': {'name': 'min_cluster_size', 'value': 40},
            'min_samples': {'name': 'min_samples', 'value': 4}
        }
    },
    'metrics': {
        'umap': {
            'spread': {
                'weight': 1.0,
                'target': 0.6,
                'epsilon': 0.1
            },
            'density_variability': {
                'weight': 1.2,
                'target': 0.4,
                'epsilon': 0.1
            },
            'entropy': {
                'weight': 1.5
            }
        },
        'hdbscan': {
            # 'cluster_persistence': {
            #     'weight': 2.0
            # },
            'noise_ratio': {
                'weight': 1.0,
                'target': 0.1,
                'epsilon': 0.05
            },
            'validity_index': {
                'weight': 1.5
            }
        }
    }
}


optim_dict_hcp = {
    'param': {
        'umap': {
            'min_dist': {'name': 'min_dist', 'value': 0.3628075254313345},
            'n_neighbors': {'name': 'n_neighbors', 'value': 10},
            'n_components': {'name': 'n_components', 'value': 2},
            'metric': {'name': 'metric', 'choices': ['euclidean']}
        },
        'hdbscan': {
            'min_cluster_size': {'name': 'min_cluster_size', 'value': 49},
            'min_samples': {'name': 'min_samples', 'value': 10}
        }
    },
    'metrics': {
        'umap': {
            'spread': {
                'weight': 1.0,
                'target': 0.6,
                'epsilon': 0.1
            },
            'density_variability': {
                'weight': 1.2,
                'target': 0.4,
                'epsilon': 0.1
            },
            'entropy': {
                'weight': 1.5
            }
        },
        'hdbscan': {
            # 'cluster_persistence': {
            #     'weight': 2.0
            # },
            'noise_ratio': {
                'weight': 1.0,
                'target': 0.1,
                'epsilon': 0.05
            },
            'validity_index': {
                'weight': 1.5
            }
        }
    }
}
