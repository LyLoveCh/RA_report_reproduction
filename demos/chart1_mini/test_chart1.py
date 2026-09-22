"""Chart-1 logic replica: the Defects4J triggering assertion, without JFreeChart.

Paper bug (Defects4J Chart-1 / RepairAgent Table III first row):
  AbstractCategoryItemRenderer.getLegendItems()
  buggy:   if (dataset != null) return empty legend;
  correct: if (dataset == null) return empty legend;

Triggering test (paper logs / Defects4J):
  AbstractCategoryItemRendererTests::test2947660
  expected:<1> but was:<0>
"""

from __future__ import annotations


def get_legend_items(plot, dataset, *, buggy: bool) -> list[str]:
    result: list[str] = []
    if plot is None:
        return result
    if buggy:
        if dataset is not None:
            return result
    else:
        if dataset is None:
            return result
    result.append("series-0")
    return result


def test_triggering_assertion_fails_on_buggy_code():
    items = get_legend_items(plot=object(), dataset=object(), buggy=True)
    assert len(items) == 0  # expected:<1> but was:<0>


def test_developer_and_repairagent_patch_passes():
    items = get_legend_items(plot=object(), dataset=object(), buggy=False)
    assert len(items) == 1


def test_null_dataset_still_returns_empty_after_fix():
    items = get_legend_items(plot=object(), dataset=None, buggy=False)
    assert items == []
