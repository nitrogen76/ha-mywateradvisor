# Installation and upgrades

1. Put this repository's integration Python files, `manifest.json`, and
   `strings.json` in `/config/custom_components/mywateradvisor/`.
2. Restart Home Assistant to load the changed code and dependencies.
3. Add MyWaterAdvisor under **Settings → Devices & services**, or open the
   existing entry's options. Choose UTC or Local for the utility's timestamps.
4. Under the Energy dashboard's water configuration, select **MyWaterAdvisor
   Hourly Water Consumption**. Remove the previous total sensor as a water source
   so the same usage is not displayed twice.

The initial import covers approximately the previous seven days. Subsequent
updates maintain cumulative hourly statistics, using the actual usage hours even
when readings arrive late. The ordinary total sensor remains available for
cards and automations, but does not generate consumption statistics itself.

Old statistics do not feed the new series and can be discarded. This code does
not automatically delete them. Deletion must target the old MyWaterAdvisor
statistics IDs in the running Home Assistant instance, after removing those old
sources from the Energy dashboard.

See README.md for correction handling, timestamp limitations and diagnostics.
