# Administrator manual

## Responsibilities

Administrators control user roles, departments, clubs, event approvals, college monitoring, certificates, resources, and system operations.

## Initial setup

Use `flask create-admin` on the application host. Supply a strong temporary password, then sign in and change it through the approved college procedure.

Never use the demo account on a production system.

## Administration

### Accounts

- Verify a student's college email and student ID before approving or modifying access.
- Disable rather than delete accounts that contain historical records.
- Do not share administrator credentials.

### Events

1. Open Event approvals.
2. Review title, description, date, capacity, venue, organizer, poster, and coordinator.
3. Approve or reject the submission and add a clear approval note.

### Departments and clubs

- Use stable department codes.
- A department cannot be deleted while users are assigned.
- Deactivate inactive clubs instead of deleting them.

### Resources

- Add classrooms, seminar halls, auditoriums, and laboratories.
- Review overlapping bookings before approving exceptional requests.
- Keep capacity and location accurate.

### Certificates

- Issue certificates only after attendance or volunteer verification.
- The public verification page is for integrity checks; it must not grant data-modification rights.
- Keep the certificate ID and PDF intact.

### Reports

Use dashboard, attendance, feedback, budget, and volunteer reports to review campus activity. Use database reports or exports for official records.

## Operations

- Monitor `/health`.
- Review application logs after failures.
- Create database backups daily.
- Test restoration monthly.
- Apply security patches using a staged upgrade and rollback plan.
- Rotate `SECRET_KEY` only through a coordinated session invalidation procedure.
