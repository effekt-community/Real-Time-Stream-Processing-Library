# Real-Time Stream Processing Library

A modular, effect-driven library for processing real-time data streams, built with [Effekt](https://effekt-lang.org/).

This library provides tools for aggregating sensor data over time windows, detecting anomalies using different strategies, and logging results. The core design principle is that everything is exposed as effects and handlers, which makes it easy to swap out components or write your own.

## Table of Contents

- [Features](#features)
- [Installation & Setup](#installation--setup)
- [Usage](#usage)
  - [Examples](#examples)
  - [Data Input Sources](#data-input-sources)
  - [Aggregation Functions](#aggregation-functions)
  - [Anomaly Detection](#anomaly-detection)
  - [Logging](#logging)
- [Architecture Overview](#architecture-overview)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [Implementation Status](#implementation-status)

---

## Features

- **Stream-based data input**: Read from CSV files, generate simulated data (normal, uniform, exponential distributions), or pull real CPU usage data
- **Windowed aggregation**: Compute running `min`, `max`, `mean`, and `median` over unbounded streams or fixed-size sliding windows
- **Anomaly detection**: Detect outliers using min-max bounds, mean threshold, or z-score methods
- **Flexible logging**: Log events and anomalies to the console or to CSV files
- **Fully composable**: All handlers in the different components share the same effect-based interface, making it easy to mix and switch them out for other or custom implementations while keeping the rest of the pipeline unchanged

---

## Installation & Setup

### Prerequisites

- [Effekt](https://effekt-lang.org/docs/getting-started) (tested with the JS backend)
- Optionally: [Nix](https://nixos.org/download.html) for reproducible builds

### Option 1: Using Effekt directly

1. Clone this repository:
   ```sh
   git clone <repo-url>
   cd Real-Time-Stream-Processing-Library
   ```

2. Make sure Effekt is installed at version `0.59.0` and available in your PATH. You can verify with:
   ```sh
   effekt --version
   ```

3. Run the main file:
   ```sh
   effekt src/main.effekt
   ```

4. Run the tests:
   ```sh
   effekt src/test.effekt
   ```

### Option 2: Using Nix

If you have Nix installed, you can use the provided flake to get a reproducible environment:

```sh
# Enter a shell with all dependencies
nix develop

# Or just run the project directly
nix run

# Build the project
nix build
```

### Editor Setup

If you're using VSCode, install the `effekt` extension for syntax highlighting and language support. The extension should also ask you to install Effekt in the newest version.

Note: Effekt is a rapidly evolving language, including changes to the standard library. If you encounter issues, ensure you're using the correct version as specified above or fix this library by implementing the necessary changes documented in the Effekt release notes..

---

## Usage

### Examples

The best way to get started is to look at the examples in [src/examples.effekt](src/examples.effekt). Here's one that monitors CPU usage, aggregates it over a sliding window, detects anomalies, and logs everything to CSV files (implemented in `src/examples.effekt`):

```js
def cpuUsageAnomalyDetectionExample(): Unit = {
  with on[IOError].panic()
  with boundary()
  with anomaly_logger::logToConsole();
  with anomaly_logger::logToFileCsvRethrow("cpu_anomalies.csv");
  with minMaxAnomalyDetector(0.0, 0.25);
  with event_logger::logToFileCsvRethrow("cpu_usage_aggregated.csv");
  
  with cpuUsagePullStream(100);
  with event_logger::logToFileCsvPull("cpu_usage_raw.csv");
  with pullStreamDelayer(100);
  aggregateMeanWindow(10);
}
```

This example shows how handlers are stacked to build a full pipeline. Each `with` statement adds another layer. Reading the second part first from top to bottom then the first part from bottom to top: raw CPU event are measured, then delayed and logged, then aggregated into a sliding mean, then checked for anomalies, and finally logged to both console and file.

You can run the examples by calling the function in `src/main.effekt` and then executing `effekt src/main.effekt`.

### Data Input Sources

The library provides various input sources that handle `read[Event]`. All input handlers share the same interface, so they can be swapped without changing the rest of the pipeline.

#### CSV Input (`src/lib/stream_input`)

| Handler | Description |
|---------|-------------|
| `csvFeed(path, valueCol, delayMs)` | Push stream from CSV file (auto-generated timestamps) |
| `csvFeed(path, valueCol, timestampCol, delayMs)` | Push stream from CSV with explicit timestamp column |
| `csvFeedPull(path, valueCol, delayMs)` | Pull stream from CSV file |
| `csvFeedPull(path, valueCol, timestampCol, delayMs)` | Pull stream from CSV with timestamps |
| `csvFeedStr(csvStr, valueCol, delayMs)` | Push stream from CSV string |
| `csvFeedStrPull(csvStr, valueCol, delayMs)` | Pull stream from CSV string |

#### Simulated Data (`src/lib/stream_input`)

| Handler | Description |
|---------|-------------|
| `normalDistributedPull(mu, sigma)` | Infinite pull stream with normal distribution |
| `uniformDistributedPull(a, b)` | Infinite pull stream with uniform distribution in [a, b] |
| `exponentialDistributedPull(lambda)` | Infinite pull stream with exponential distribution |

#### Real Sensor Data (`src/lib/cpu_utilization_input`)

| Handler | Description |
|---------|-------------|
| `cpuUsagePullStream()` | Infinite pull stream of CPU usage (0.0 to 1.0), Node.js only |
| `cpuUsagePullStream(limit)` | Pull stream limited to `limit` events |

#### Stream Utilities (`src/lib/stream_input`)

| Handler | Description |
|---------|-------------|
| `pullStreamDelayer(delayMs)` | Adds delay between reads |
| `pullStreamLimiter(maxEvents)` | Stops stream after `maxEvents` |
| `pushToPullStream[T]()` | Converts push stream to pull stream |

Usage examples are provided in the `examples` namespace within each component file.

### Aggregation Functions

All aggregators read events via `read[Event]` and emit aggregated results via `emit[Event]`.

| Function | Description | Space | Time per event |
|----------|-------------|-------|----------------|
| `aggregateMin()` | Running minimum over all events | O(1) | O(1) |
| `aggregateMax()` | Running maximum over all events | O(1) | O(1) |
| `aggregateMean()` | Running mean over all events | O(1) | O(1) |
| `aggregateMedian()` | Running median over all events | O(n) | O(n log n) |
| `aggregateMinWindow(size)` | Minimum over sliding window | O(size) | O(1) |
| `aggregateMaxWindow(size)` | Maximum over sliding window | O(size) | O(1) |
| `aggregateMeanWindow(size)` | Mean over sliding window | O(size) | O(1) |
| `aggregateMedianWindow(size)` | Median over sliding window | O(size) | O(n log n) |


### Anomaly Detection

The library provides three anomaly detection strategies (`src/lib/anomaly_detection`). Each detector reads events via `read[Event]` and calls the `AnomalyDetection` interface (`anomaly()` or `noAnomaly()`).

| Detector | Description |
|----------|-------------|
| `minMaxAnomalyDetector(min, max)` | Flags events outside [min, max]. Score = distance outside range |
| `meanThresholdAnomalyDetector(threshold)` | Flags events where \|value - mean\| > threshold. Score = deviation |
| `zScoreAnomalyDetector(zThreshold)` | Flags events where \|z-score\| > threshold. Score = z-score |

All detectors maintain O(1) space and time complexity per event using the `Counter` record for running statistics.

Usage examples are provided in the `examples` namespace within `anomaly_detection.effekt`.

### Logging

The library provides handlers to log events or anomaly evaluations. "Rethrow" variants forward events after logging, allowing multiple loggers to be chained.

#### Event Logging (`src/lib/event_logger`)

Handles `emit[Event]` (push) or `read[Event]` (pull) effects.

| Handler | Description |
|---------|-------------|
| `logToConsole()` | Logs emitted events to console |
| `logToConsoleRethrow()` | Logs to console and forwards events |
| `logToConsolePull()` | Logs pulled events to console |
| `logToFileCsv(path)` | Logs emitted events to CSV file |
| `logToFileCsvRethrow(path)` | Logs to CSV and forwards events |
| `logToFileCsvPull(path)` | Logs pulled events to CSV file |

#### Anomaly Logging (`src/lib/anomaly_logger`)

Handles the `AnomalyDetection` effect.

| Handler | Description |
|---------|-------------|
| `logAnomaliesToConsole()` | Logs only anomalies to console |
| `logAnomaliesToConsoleRethrow()` | Logs anomalies to console and forwards |
| `logToConsole()` | Logs all events (anomalies + normal) to console |
| `logToConsoleRethrow()` | Logs all to console and forwards |
| `logToFileCsv(path)` | Logs all events to CSV file |
| `logToFileCsvRethrow(path)` | Logs all to CSV and forwards |
| `logAnomaliesToFileCsv(path)` | Logs only anomalies to CSV file |
| `logAnomaliesToFileCsvRethrow(path)` | Logs anomalies to CSV and forwards |

Usage examples are provided in the `examples` namespace within each logger file.

---

## Architecture Overview

The library is built around Effekt's effect system. Components communicate through effects (`read[Event]`, `emit[Event]`, `AnomalyDetection`) that get handled by outer handlers. This design enables:

- **Composability**: Stack handlers to build pipelines
- **Exchangeability**: Swap any handler for another without changing the rest of the pipeline
- **Extensibility**: Add custom handlers that implement the same effect interfaces

A typical pipeline stacks handlers with `with` statements:

```js
with anomaly_logger::logToConsole()         // 4. Handle anomaly results
with minMaxAnomalyDetector(0.0, 0.25)       // 3. Detect anomalies
with cpuUsagePullStream(100)                // 0. Provide events
with pullStreamDelayer(100)                 // 1. Add delay between reads
aggregateMean()                             // 2. Aggregate events
```

For detailed architecture documentation, implementation details, and guidelines for extending the library, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Running Tests

The test suite covers aggregation, anomaly detection, and stream input:

```sh
effekt src/test.effekt
```

Or with Nix:

```sh
nix develop -c effekt src/test.effekt
```

Tests use the `test` module from Effekt's standard library and return exit code 0 on success, 1 on failure.

---

## Project Structure

```
.
├── src/
│   ├── main.effekt           # Main entry point
│   ├── test.effekt           # Test runner
│   ├── examples.effekt       # Usage examples
│   ├── lib.effekt            # Library re-exports
│   ├── lib/                  # Library modules
│   │   ├── aggregation.effekt
│   │   ├── anomaly_detection.effekt
│   │   ├── anomaly_logger.effekt
│   │   ├── counter.effekt
│   │   ├── cpu_utilization_input.effekt
│   │   ├── csv.effekt
│   │   ├── event.effekt
│   │   ├── event_logger.effekt
│   │   ├── stream_input.effekt
│   │   ├── timestamp.effekt
│   │   └── typeconversion.effekt
│   └── test/                 # Test modules and data
│       ├── aggregation_test.effekt
│       ├── anomaly_detection_test.effekt
│       ├── stream_input_test.effekt
│       ├── lib.effekt
│       ├── testdata.csv
│       └── testdata_with_timestamp.csv
├── flake.nix                 # Nix flake configuration
├── flake.lock                # Nix lockfile
├── PROJECT_SPEC.md           # Project specification
├── ARCHITECTURE.md           # Developer/architecture documentation
├── LICENSE
└── README.md
```

---

## Implementation Status

All requirements from the project specification have been implemented:

**Core Features (Must-have)**:
- ✅ Stream-based data input with simulated distributions (uniform, normal, exponential)
- ✅ Window-based aggregation (min, max, mean, median) for both unbounded and sliding windows
- ✅ Anomaly detection with min-max scope and z-score handlers
- ✅ Console and CSV file logging
- ✅ Example setups demonstrating the full pipeline

**Extended Features (Can-have)**:
- ✅ Real-time CPU usage input stream (via Node.js FFI)
- ✅ Working example with real CPU sensor data

**Additional Features** (not directly in original spec, added for smoother library usage):
- Pull stream utilities (`pullStreamDelayer`, `pullStreamLimiter`) for controlling stream timing and length
- Rethrow variants of loggers (`logToFileCsvRethrow`, ...) that forward events after logging, useful for chaining multiple loggers or adding loggers in the middle of the pipeline
- Pull-based logging handlers (`logToConsolePull`, `logToFileCsvPull`) for direct integration into pull pipelines to log raw input data

---

## Acknowledgments

This project was developed as part of the "Programming with Effekt" course.
