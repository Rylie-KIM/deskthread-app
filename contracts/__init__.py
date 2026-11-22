"""Frozen contracts between the parts of DeskThread.

Everything here is an interface or a plain data shape. Only the main session changes this
package; a change bumps CONTRACT_VERSION (dev rule R14).
"""

CONTRACT_VERSION = (
    "1.6"  # 1.1 demo; 1.2 no locked; 1.3 models; 1.4 progress; 1.5 status; 1.6 folders
)
