# URL Visit Tracker Bruno collection

Open this directory as a collection in Bruno. Select **Local 8080** when using
`make port-forward-app` (the default port is 8080), or **Local 8000** for a
standalone server on port 8000. Change `baseUrl` in the chosen environment if
your port differs.

Run the numbered requests in order for a complete workflow. Request 02 generates
a unique custom code before sending and stores it as the runtime variable
`customCode`. Requests 03–06 use that code. Request 07 asks the backend to
generate a code. Requests 08–09 create the other supported policy types. Request
10 captures a one-visit link as `limitedCode` for requests 11–12. Runtime
variables persist for the current Bruno session, so run the creation request
again if a later request has an unresolved variable.

`collection.bru` holds shared sample inputs. Edit `destinationUrl`,
`ttlSeconds`, `demoPassword`, or `allowedIp` there for your environment. The
sample password is only for development. Password and IP policy admission on
redirect is not implemented yet; those requests exercise creation and storage.

Redirect requests disable automatic redirect following so you can inspect the
API's `302` status and `Location` header without contacting the destination.

You can also run the sequence with Bruno CLI from this directory:

```sh
bru run --env "Local 8080"
```

The collection creates and disables links in the selected environment, so use a
development instance for the full sequence.
