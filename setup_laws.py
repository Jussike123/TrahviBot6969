"""
Initial setup script - Create default laws in the database
Run this once after creating the database
"""

from database.db import init_database, insert_law, get_all_laws

def setup_default_laws():
    """Insert default laws into the database"""
    
    init_database()
    
    default_laws = [
        ("Speeding", 150.00, "Exceeding speed limit"),
        ("Running Red Light", 200.00, "Failed to stop at red light"),
        ("Reckless Driving", 300.00, "Dangerous driving behavior"),
        ("No License", 400.00, "Driving without valid license"),
        ("Expired Registration", 100.00, "Vehicle registration expired"),
        ("Parking Violation", 75.00, "Illegal parking"),
        ("Hit and Run", 500.00, "Leaving scene of accident"),
        ("Drunk Driving", 1000.00, "Driving under influence"),
        ("Expired Insurance", 200.00, "No valid vehicle insurance"),
        ("Using Phone While Driving", 125.00, "Texting or calling while driving"),
    ]
    
    # Get existing laws
    existing = get_all_laws()
    existing_names = {name for _, name, _ in existing}
    
    added = 0
    for law_name, fine, description in default_laws:
        if law_name not in existing_names:
            try:
                insert_law(law_name, fine, description)
                print(f"✓ Added law: {law_name} (${fine:.2f})")
                added += 1
            except Exception as e:
                print(f"✗ Failed to add {law_name}: {e}")
        else:
            print(f"- Law already exists: {law_name}")
    
    print(f"\n✓ Setup complete! Added {added} new laws.")
    print("\nCurrent laws:")
    for law_id, name, fine in get_all_laws():
        print(f"  • {name}: ${fine:.2f}")

if __name__ == "__main__":
    setup_default_laws()
