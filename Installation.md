# Installation Guide

## Overview

This guide explains how to install the MyWaterAdvisor Home Assistant
integration.

## Prerequisites

-   Home Assistant (Home Assistant OS or Core)
-   SSH or terminal access to your Home Assistant config directory
-   Git installed (or ability to copy files manually)

## Step 1: Clone the Repository

Navigate to your Home Assistant `custom_components` directory:

    cd /config/custom_components

Clone the repository:

    git clone https://github.com/nitrogen76/ha-mywateradvisor.git

This should create:

    /config/custom_components/ha-mywateradvisor/

## Step 2: Restart Home Assistant

Restart Home Assistant to load the new integration.

## Step 3: Add Integration

1.  Go to **Settings → Devices & Services**
2.  Click **Add Integration**
3.  Search for **MyWaterAdvisor**
4.  Enter your:
    -   Username (email)
    -   Password

## Step 4: Verify Sensors

After setup, you should see: - Water usage total sensor - Debug sensor

## Notes

-   The integration will begin pulling data immediately
-   First run establishes a baseline (no backfill spike)
-   Only real (non-estimated) readings are used for totals

## Troubleshooting

-   Check logs under **Settings → System → Logs**
-   Enable debug logging if needed
-   Verify credentials by testing with the CLI tool

## Updating

To update:

    cd /config/custom_components/mywateradvisor
    git pull

Then restart Home Assistant.
