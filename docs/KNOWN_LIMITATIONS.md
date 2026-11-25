# Known limitations

## Infrastructure

- The application has not been deployed to a college domain or target server.
- Docker availability could not be verified in the development environment.
- A production MySQL instance and credentials were not provided.
- HTTPS certificates and DNS were not configured.
- Production responsive-device testing was not performed.

## Data and operations

- Demonstration accounts must not be enabled in production.
- Database and file backups require college infrastructure and scheduled automation.
- Log retention, SIEM integration, and monitoring are not configured.
- Email/SMS delivery is not implemented; notifications are in-app only.
- QR attendance is a link-based implementation and requires controlled network/device use.
- Certificate revocation is represented by the `is_valid` field but no administrator UI is included yet.

## Performance and scale

- The application requires load testing against realistic college traffic.
- Cache infrastructure and a CDN are not configured.
- Upload storage is local unless operators map persistent volumes or object storage.
- Database indexes should be reviewed after observing production query plans.
- The rule-based assistance features are deliberately not generative AI.
