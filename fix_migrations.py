import os
import shutil

# Get all app directories
app_dirs = [
    'apps/organizations',
    'apps/users',
    'apps/pilots',
    'apps/notifications',
    'apps/payments'
]

# For each app, create a migrations directory with just __init__.py
for app_dir in app_dirs:
    migrations_dir = os.path.join(app_dir, 'migrations')
    
    # Create clean directory
    if os.path.exists(migrations_dir):
        shutil.rmtree(migrations_dir)
    
    os.makedirs(migrations_dir, exist_ok=True)
    
    # Create empty __init__.py
    with open(os.path.join(migrations_dir, '__init__.py'), 'w') as f:
        pass
    
    print(f"Reset migrations for {app_dir}")

print("Migration reset complete. Now run 'makemigrations' for each app.")
