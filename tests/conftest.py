from __future__ import annotations

import pytest

from src.generate_synthetic_data import generate_dataset


@pytest.fixture()
def sample_dataset():
    return generate_dataset(shipment_count=45, vehicle_count=10, seed=123)

