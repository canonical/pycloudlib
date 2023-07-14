# Resource Cleanup

By default, pycloudlib will **not** automatically cleanup created resources because there are use cases for inspecting resources launched by pycloudlib after pycloudlib has exited.

## Performing Cleanup

The easiest way to ensure cleanup happens is to use the `cloud` and `instance` context managers. For example, using EC2:

```python
from pycloudlib.ec2.cloud import EC2


with EC2(tag="example") as cloud:
    with cloud.launch("your-ami") as instance:
        output = instance.execute("cat /etc/lsb-release").stdout


print(output)
```

When the context manager exits (even if due to an exception), all resources that were created during the lifetime of the `Cloud` or `Instance` object will automatically be cleaned up. Any exceptions raised during the cleanup process will be raised.

Alternatively, if you don't want to use context managers, you can manually cleanup all resources using the `.clean()` method on `Cloud` objects and the `.delete()` method on `Instance` objects. For example, using EC2:

```python
from pycloudlib.ec2.cloud import EC2


cloud = EC2(tag="example")
instance = cloud.launch("your-ami")
instance.execute("cat /etc/lsb-release").stdout

instance_cleanup_exceptions: List[Exception] = instance.delete()
cloud_cleanup_exceptions: List[Exception] = cloud.clean()
```

Things to note:

* Exceptions that occur during cleanup aren't automatically raised and are instead returned. This is to is to prevent a failure in one stage of cleanup from affecting another.
* Resources can still leak if an exception is raised between creating the object and cleaning it up. To ensure resources are not leaked, the body of code between launch and cleanup must be wrapped in an exception handler.

Because of these reasons, the context manager approach should be preferred.
