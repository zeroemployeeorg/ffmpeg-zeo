# Graph JSON

A `Graph` has `inputs`, `filters`, `outputs`, optional `global_args`, and `overwrite` (`always` | `never`).

```json
{
  "inputs": [{"id": "in1", "filename": "in.mp4", "kwargs": {}}],
  "filters": [{
    "id": "f1",
    "name": "scale",
    "inputs": [{"node_id": "in1", "pad": null, "selector": "v"}],
    "args": [1280, -2],
    "kwargs": {}
  }],
  "outputs": [{
    "id": "out1",
    "filename": "out.mp4",
    "inputs": [{"node_id": "f1", "pad": null, "selector": null}],
    "kwargs": {"vcodec": "libx264"}
  }],
  "global_args": [],
  "overwrite": "always"
}
```
