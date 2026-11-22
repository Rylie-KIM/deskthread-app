"""Frozen contracts between the parts of DeskThread.

Everything here is an interface or a plain data shape. Only the main session changes this
package; a change bumps CONTRACT_VERSION (dev rule R14).
"""

CONTRACT_VERSION = "1.1"  # 1.1: SessionInfo.demo_folder (additive)
