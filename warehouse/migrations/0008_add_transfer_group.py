from django.db import migrations, models
import uuid

class Migration(migrations.Migration):
    dependencies = [
        ('warehouse', '0006_remove_transaction_shift_and_more'),
    ]

    operations = [
        # FIXED: This operation was creating a duplicate column error because 
        # migration 0006 already adds 'transfer_group_id' to Transaction.
        # Keeping the file but removing operations to preserve migration history chain.
    ]