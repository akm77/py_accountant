from sqlalchemy import inspect

from infrastructure.persistence.sqlalchemy.models import (
    Base,
    make_engine,
)


def test_indexes_present_sqlite_memory():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    j_ix = {ix['name'] for ix in insp.get_indexes('journals')}
    t_ix = {ix['name'] for ix in insp.get_indexes('transaction_lines')}
    assert 'ix_journals_occurred_at' in j_ix
    assert 'ix_tx_lines_account_full_name' in t_ix
    assert 'ix_tx_lines_currency_code' in t_ix
    assert 'ix_tx_lines_account_journal' in t_ix

