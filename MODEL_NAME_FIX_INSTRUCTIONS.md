# Model Name Fix - Test Instructions

## What Was Changed

The `emuses models install` command now uses the **folder name** as the default model name instead of any name found in existing manifest files.

## Before the Fix

```bash
emuses models install "/path/to/my_descriptive_model_folder"
# Result: Name: 'hdbscan_model' (from existing manifest)
```

## After the Fix

```bash
emuses models install "/path/to/my_descriptive_model_folder"
# Result: Name: 'my_descriptive_model_folder' (from folder name)
```

## Test Your Specific Case

Try running your original command again:

```bash
emuses models install "/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/model_registry_final_one_target"
```

**Expected result**: Name should now be `'model_registry_final_one_target'` instead of `'hdbscan_model'`.

## Behavior Summary

1. **User provides `--name`**: Uses the provided name (highest priority)
   ```bash
   emuses models install /path/to/folder --name "My Custom Name"
   # Result: Name: 'My Custom Name'
   ```

2. **No `--name` provided**: Uses folder name (NEW BEHAVIOR)
   ```bash
   emuses models install /path/to/folder
   # Result: Name: 'folder'
   ```

3. **Backward compatibility**: All existing functionality preserved

## Files Changed

- `emuses/tools/local_model_registry.py` - Modified the naming logic in `install_model()` method

## Verification

If you still see `'hdbscan_model'` after this change, it means:
1. You provided `--name hdbscan_model` explicitly, OR
2. There's another code path we haven't identified

In case #2, please share the exact command and output so we can investigate further.
