# Architecture & Developer Documentation

This document provides an in-depth look at the architecture of the Real-Time Stream Processing Library, implementation details, and guidelines for extending the library with custom components.

## Table of Contents

- [Architecture Overview](#architecture-overview)
  - [Effects and Handlers](#effects-and-handlers)
  - [Handler Exchangeability](#handler-exchangeability)
  - [Stream Model](#stream-model)
  - [Module Structure](#module-structure)
- [Implementation Details](#implementation-details)
  - [The Counter Record](#the-counter-record)
  - [Sliding Window Implementation](#sliding-window-implementation)
  - [File I/O](#file-io)
  - [FFI Usage](#ffi-usage)
- [Extending the Library](#extending-the-library)
  - [Writing a Custom Anomaly Detector](#writing-a-custom-anomaly-detector)
  - [Writing a Custom Input Source](#writing-a-custom-input-source)
  - [Writing a Custom Logger](#writing-a-custom-logger)
- [Acknowledgments](#acknowledgments)

---

## Architecture Overview

### Effects and Handlers

The entire library is built around Effekt's effect system. Instead of calling functions that return values directly to connect the components, components communicate through effects that get handled by outer handlers from another component.

The main effects used are:

- **`read[Event]`**: Pull-based stream input. When a component needs the next event, it performs `do read[Event]()`. A handler somewhere up the call stack provides the actual value.
- **`emit[Event]`**: Push-based stream output. Components emit results using `do emit(event)`. Handlers decide what to do with each value.
- **`AnomalyDetection`**: Interface with `anomaly()` and `noAnomaly()` operations. Anomaly detectors call these, and handlers decide how to react (log, alert, store, etc.).
- **`stop`**: Used to signal the end of the stream.

The benefit of this design is composability and exchangability of handlers: you stack handlers from the different components to build pipelines:

```js
with anomaly_logger::logToConsole()         // 4. Handle anomaly results
with minMaxAnomalyDetector(0.0, 0.25)       // 3. Detect anomalies
with cpuUsagePullStream(100)                // 0. Provide events
with pullStreamDelayer(100)                 // 1. Add delay between reads
aggregateMean()                             // 2. Aggregate events
```

Each layer shares the same handler "interface", making components independent and handlers swappable. Also new handlers can be easily added without changing the whole pipeline (see [Handler Exchangeability](#handler-exchangeability)).
The downside of this implementation is that the logical flow can be harder to follow, as the stream input is in the middle of the stack (see example above).

### Handler Exchangeability

A key design principle is that **handlers within each component category share the same interface**. This means you can swap out any handler for another without changing the rest of your pipeline.

For example, all anomaly loggers handle the `AnomalyDetection` effect the same way:
- `logAnomaliesToConsole()` - prints only anomalies
- `logToConsole()` - prints all events
- `logToFileCsv(path)` - writes to CSV
- `logToFileCsvRethrow(path)` - writes to CSV AND forwards to next handler

Switching from console to file logging is just changing one line. The rest of the pipeline stays exactly the same.

Similarly for the rest of the library - whether you use `csvFeedPull()`, `normalDistributedPull()`, or `cpuUsagePullStream()`, they all provide events via `read[Event]`, so any aggregator works with any input source and any anomaly detector works with any aggregator.

### Stream Model

The library uses two stream models:

1. **Pull streams**: The consumer requests data by performing `read[Event]`. The handler decides where the data comes from. This is lazy—no work happens until someone reads.

2. **Push streams**: The producer emits data by performing `emit[Event]`. The handler decides what to do with each value.

You can convert between them using `pushToPullStream`:

```js
pushToPullStream[Event]() { 
  // push stream producer (emits events)
} { 
  // pull stream consumer (reads events)
}
```

Since we do not work with real parallelism or concurrency here, it is not possible to run the data input and the aggregation/anomaly detection in separate thread and let them communicate via a buffer. This could be an interesting extension for future work since it then could handle bursts of incoming data. With this implementation the aggregator pulls data as fast as it can process it from the input source. Therefore the input source doesn't run independently and hast to wait until the aggregator requests the next event.

### Module Structure

```
src/lib/
├── event.effekt              # Event record definition and utilities
├── counter.effekt            # Running statistics (sum, mean, variance, stddev)
├── aggregation.effekt        # Aggregation functions (min, max, mean, median)
├── anomaly_detection.effekt  # Anomaly detection strategies
├── stream_input.effekt       # CSV and simulated data sources
├── cpu_utilization_input.effekt  # Real CPU usage (Node.js FFI)
├── event_logger.effekt       # Logging handlers for events
├── anomaly_logger.effekt     # Logging handlers for anomaly results
├── csv.effekt                # CSV parsing utilities (from @jiribenes, adapted as described in the file)
├── timestamp.effekt          # Timestamp utilities
└── typeconversion.effekt     # String to number conversions
```

---

## Implementation Details

### The Counter Record

The `Counter` record is used internally by aggregators and detectors to compute running statistics in O(1) space and time complexity per event provided:

```js
record Counter(sum: Double, sumSq: Double, count: Int)
```

It tracks the sum and sum of squares, which allows computing mean, variance, and standard deviation without storing all values. This is based on the mathematical identity:

$$\text{Var}(X) = \frac{1}{n-1}\left(\sum x_i^2 - \frac{(\sum x_i)^2}{n}\right)$$

### Sliding Window Implementation

Windowed aggregations use a fixed-size array as a circular buffer. For min/max, we only recompute from scratch when the outgoing value equals the current min/max. This gives O(1) amortized time in practice.

### File I/O

To support logging to CSV files in long-running processes, the data is buffered and flushed periodically. This reduces the number of write operations and improves performance.

### FFI Usage

The library uses minimal FFI:
- `infinity` and `negInfinity` for initial min/max values (JS `Infinity`)
- `getCpuUsage()` for reading CPU stats via Node.js `os` module
- `toDoubleUnsafe(String)`, `isNaN(String)` and `toDouble(String)` for string-to-number conversions

---

## Extending the Library

### Writing a Custom Anomaly Detector

To add your own detection strategy, write a function that reads events and calls the `AnomalyDetection` effect:

```js
def myCustomDetector(param: Double): Unit / { read[Event], AnomalyDetection } = {
  with boundary
  while (true) {
    val ev = do read[Event]()
    // your detection logic here
    if (isAnomalous) {
      do anomaly(AnomalyEvaluation(ev, true, score))
    } else {
      do noAnomaly(AnomalyEvaluation(ev, false, 0.0))
    }
  }
}
```

### Writing a Custom Input Source

Implement a handler for `read[Event]`:

```js
def myDataSource() { body: () => Unit / read[Event] }: Unit = {
  try body() with read[Event] {
    val nextEvent = // fetch from somewhere
    resume { nextEvent }
  }
}
```

### Writing a Custom Logger

Handle the `AnomalyDetection` or `emit[Event]` effects:

```js
def myLogger() { body: () => Unit / emit[Event] }: Unit = {
  try body() with emit[Event] { ev =>
    // do something with ev
    resume(())
  }
}
```

---

## Acknowledgments

The library design follows the principle of keeping the FFI surface minimal and implementing as much as possible in pure Effekt.