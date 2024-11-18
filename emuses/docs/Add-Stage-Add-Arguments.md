# Adding New Stages and Arguments to the EMUSESPipeline

This guide provides step-by-step instructions on how to add a new processing stage and command-line argument to the `EMUSESPipeline`. This ensures the pipeline remains modular, maintainable, and flexible.

## Table of Contents

- [Adding a New Stage](#adding-a-new-stage)
  - [1. Create the New Stage Class](#1-create-the-new-stage-class)
  - [2. Import and Integrate the New Stage](#2-import-and-integrate-the-new-stage)
  - [3. Ensure Data Flow Between Stages](#3-ensure-data-flow-between-stages)
  - [4. Implement Error Handling and Logging](#4-implement-error-handling-and-logging)
  - [5. Test the New Stage](#5-test-the-new-stage)
- [Adding a New Argument](#adding-a-new-argument)
  - [1. Determine the Scope of the Argument](#1-determine-the-scope-of-the-argument)
  - [2. Add the Argument to the Appropriate Parser](#2-add-the-argument-to-the-appropriate-parser)
  - [3. Update the Pipeline Configuration](#3-update-the-pipeline-configuration)
  - [4. Access the Argument in Code](#4-access-the-argument-in-code)
  - [5. Update Help Messages and Defaults](#5-update-help-messages-and-defaults)
  - [6. Validate the Argument](#6-validate-the-argument)
- [Example: Adding a Normalization Stage and Argument](#example-adding-a-normalization-stage-and-argument)
  - [1. Add the `--normalize` Argument](#1-add-the---normalize-argument)
  - [2. Update `PipelineConfig` for the New Argument](#2-update-pipelineconfig-for-the-new-argument)
  - [3. Create the Normalization Stage Class](#3-create-the-normalization-stage-class)
  - [4. Integrate the Normalization Stage](#4-integrate-the-normalization-stage)
  - [5. Adjust Data Flow](#5-adjust-data-flow)
  - [6. Test the Implementation](#6-test-the-implementation)
- [Summary](#summary)
- [Best Practices](#best-practices)

---

## Adding a New Stage

### 1. Create the New Stage Class

- **Location**: Place the new stage class in the `pipelines` folder alongside other stages (e.g., `umap_stage.py`, `clustering_stage.py`).
- **Filename**: Name the file appropriately, such as `my_new_stage.py`.

```python
# pipelines/my_new_stage.py

import logging
from emuses.pipelines import PipelineStage


class MyNewStage(PipelineStage):
    def __init__(self, config, **kwargs):
        super().__init__(config)
        # Initialize any required attributes
        self.some_parameter = kwargs.get('some_parameter', default_value)

    def run(self, **kwargs):
        logger = logging.getLogger(__name__)
        logger.info("Running My New Stage")

        # Access inputs from previous stages if needed
        previous_output = kwargs.get('previous_output')

        # Implement the main logic of the stage
        result = self.process_data(previous_output)

        # Return outputs to be used by subsequent stages
        return {'my_new_stage_output': result}

    def process_data(self, data):
        # Implement the processing logic
        processed_data = data  # Placeholder for actual processing
        return processed_data
```

**Explanation:**

- Inherit from `PipelineStage`.
- Implement `__init__` and `run` methods.
- Use `**kwargs` in `run` to accept inputs from previous stages.
- Return a dictionary of outputs.

### 2. Import and Integrate the New Stage

- **Import the Stage in `main.py`**:

  ```python
  # main.py

  from emuses.pipelines import MyNewStage
  ```

- **Add the Stage to the Pipeline**:

  ```python
  # main.py

  if args.command == 'full':
      # Existing stages
      # ...

      # Instantiate and add the new stage
      my_new_stage = MyNewStage(pipeline.config, some_parameter=value)
      pipeline.add_stage(my_new_stage)

      # Continue with other stages
      # ...
  ```

**Explanation:**

- Instantiate the new stage with necessary parameters.
- Use `pipeline.add_stage()` to include it in the pipeline.
- Place it in the correct order based on dependencies.

### 3. Ensure Data Flow Between Stages

- **Update `EMUSESPipeline.run()` if needed**:

  ```python
  # pipelines/emuses_pipeline.py

  class EMUSESPipeline:
      # ...

      def run(self):
          data = {}
          for stage in self.stages:
              result = stage.run(**data)
              data.update(result)  # Update the data with outputs from the current stage
              self.results.update(result)  # Optionally store results
  ```

**Explanation:**

- Each stage receives inputs via `**kwargs`.
- Outputs are added to `data` for subsequent stages.

### 4. Implement Error Handling and Logging

- **Add Logging Statements**:

  ```python
  logger.info("Starting processing in My New Stage")
  # ...
  logger.info("Completed processing in My New Stage")
  ```

- **Include Error Handling**:

  ```python
  try:
      # Processing logic
  except Exception as e:
      logger.error(f"An error occurred in My New Stage: {e}")
      raise
  ```

### 5. Test the New Stage

- **Unit Test**: Test the stage independently.
- **Integration Test**: Run the pipeline with the new stage included.

---

## Adding a New Argument

### 1. Determine the Scope of the Argument

- **Global Argument**: Applies to all commands.
- **Command-Specific Argument**: Applies only to certain subcommands.

### 2. Add the Argument to the Appropriate Parser

- **For Common Arguments Using a Parent Parser**:

  ```python
  def get_common_args_parser():
      parser = argparse.ArgumentParser(add_help=False)
      parser.add_argument('--new_arg', type=str, help='Description of the new argument')
      return parser

  common_args_parser = get_common_args_parser()
  ```

- **Include the Parent Parser in Subparsers**:

  ```python
  full_parser = subparsers.add_parser(
      'full',
      parents=[common_args_parser, other_parent_parsers],
      help='Run the full pipeline'
  )
  ```

- **For Command-Specific Arguments**:

  ```python
  full_parser.add_argument('--new_arg', type=str, help='Description of the new argument')
  ```

### 3. Update the Pipeline Configuration

- **Add the Argument to `PipelineConfig`**:

  ```python
  # pipelines/pipeline_config.py

  @dataclass
  class PipelineConfig:
      # Existing fields
      # ...

      new_arg: str = field(init=False)

      def __post_init__(self):
          # Existing initialization
          # ...

          self.new_arg = getattr(self.args, 'new_arg', default_value)
  ```

### 4. Access the Argument in Code

- **In Stages or Components**:

  ```python
  # pipelines/my_new_stage.py

  class MyNewStage(PipelineStage):
      def __init__(self, config):
          super().__init__(config)
          self.new_arg = config.new_arg  # Access the new argument

      def run(self, **kwargs):
          # Use self.new_arg as needed
          if self.new_arg == 'some_value':
              # Implement logic based on the argument value
              pass
  ```

### 5. Update Help Messages and Defaults

- **Provide Clear Descriptions**:

  ```python
  parser.add_argument('--new_arg', type=str, default='default_value',
                      help='Description of the new argument')
  ```

### 6. Validate the Argument

- **Include Validation Logic**:

  ```python
  # pipelines/my_new_stage.py

  def run(self, **kwargs):
      if self.new_arg not in valid_values:
          raise ValueError(f"Invalid value for new_arg: {self.new_arg}")
  ```

---

## Example: Adding a Normalization Stage and Argument

### 1. Add the `--normalize` Argument

- **Define a Parent Parser for Normalization Arguments**:

  ```python
  def get_normalization_parser():
      parser = argparse.ArgumentParser(add_help=False)
      parser.add_argument('--normalize', choices=['minmax', 'zscore'], default=None,
                          help='Apply normalization to input data')
      return parser

  normalization_parser = get_normalization_parser()
  ```

- **Include in Relevant Subparsers**:

  ```python
  full_parser = subparsers.add_parser(
      'full',
      parents=[normalization_parser, other_parent_parsers],
      help='Run the full pipeline'
  )
  ```

### 2. Update `PipelineConfig` for the New Argument

```python
# pipelines/pipeline_config.py

@dataclass
class PipelineConfig:
    # Existing fields
    # ...

    normalize: str = field(init=False)

    def __post_init__(self):
        # Existing initialization
        # ...

        self.normalize = getattr(self.args, 'normalize', None)
```

### 3. Create the Normalization Stage Class

```python
# pipelines/normalization_stage.py

import logging
import numpy as np
from emuses.pipelines import PipelineStage


class NormalizationStage(PipelineStage):
    def __init__(self, config):
        super().__init__(config)
        self.method = config.normalize

    def run(self, **kwargs):
        logger = logging.getLogger(__name__)
        logger.info(f"Running Normalization Stage with method: {self.method}")

        input_matrix = kwargs.get('input_matrix')

        if self.method == 'minmax':
            # Apply min-max normalization
            normalized_matrix = (input_matrix - np.min(input_matrix, axis=0)) /
                                (np.max(input_matrix, axis=0) - np.min(input_matrix, axis=0))
        elif self.method == 'zscore':
            # Apply z-score normalization
            normalized_matrix = (input_matrix - np.mean(input_matrix, axis=0)) /
                                np.std(input_matrix, axis=0)
        else:
            normalized_matrix = input_matrix  # No normalization

        # Return the normalized matrix for subsequent stages
        return {'input_matrix': normalized_matrix}
```

### 4. Integrate the Normalization Stage

- **Import the Stage in `main.py`**:

  ```python
  from emuses.pipelines import NormalizationStage
  ```

- **Add the Stage to the Pipeline**:

  ```python
  if args.command == 'full':
      # Existing setup
      # ...

      # Add Normalization Stage if specified
      if pipeline.config.normalize:
          normalization_stage = NormalizationStage(pipeline.config)
          pipeline.add_stage(normalization_stage)

      # Continue with other stages
      umap_stage = UMAPStage(pipeline.config)
      pipeline.add_stage(umap_stage)
      # ...
  ```

### 5. Adjust Data Flow

- **Ensure Subsequent Stages Use Normalized Data**:

  ```python
  # pipelines/emuses_pipeline.py

  def run(self):
      data = {'input_matrix': self.input_matrix}
      for stage in self.stages:
          result = stage.run(**data)
          data.update(result)
          self.results.update(result)
  ```

- **Modify Stages to Access `input_matrix` from `data`**:

  ```python
  # pipelines/umap_stage.py

  class UMAPStage(PipelineStage):
      def run(self, **kwargs):
          input_matrix = kwargs.get('input_matrix')
          # Use input_matrix for UMAP processing
  ```

### 6. Test the Implementation

- **Run the Pipeline with Normalization**:

  ```bash
  python main.py full output_folder_path input_dataset_path --normalize zscore
  ```

---

## Summary

**Adding a New Stage:**

- **Create the Stage Class** in the `pipelines` folder.
- **Implement `__init__` and `run` methods**.
- **Add the Stage to the Pipeline** in `main.py`.
- **Ensure Data Flow** by passing and receiving data via `**kwargs`.
- **Test** both independently and within the pipeline.

**Adding a New Argument:**

- **Add to the Argument Parser**.
- **Update `PipelineConfig`** to include the new argument.
- **Access the Argument** in code via `self.config`.
- **Update Help Messages** with clear descriptions.
- **Validate** the argument's value if necessary.

---

## Best Practices

- **Maintain Modularity**: Keep stages self-contained.
- **Ensure Clarity**: Use descriptive names and comments.
- **Handle Errors Gracefully**: Include informative error messages.
- **Document Changes**: Update documentation to reflect new features.
- **Test Thoroughly**: Verify functionality at each step.

---