import sys
import unittest
from pathlib import Path
import importlib.util as ilu

spec = ilu.spec_from_file_location("rubika_adapter_module",
                                   Path(__file__).resolve().parents[1] / "apps" / "rubika-bot" / "adapter.py")
mod = ilu.module_from_spec(spec)
spec.loader.exec_module(mod)
RubikaAdapter = mod.RubikaAdapter


class RubikaAdapterTests(unittest.TestCase):
    def test_instantiation_refuses_with_clear_reason(self):
        """عمداً هنوز پیاده نشده؛ باید واضح بگوید چرا، نه اینکه ساکت کار نکند."""
        with self.assertRaises(NotImplementedError) as ctx:
            RubikaAdapter()
        self.assertIn("غیررسمی", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
