#!/usr/bin/env python3
"""
Database setup script for the MSSQL MCP Server.
This script helps set up initial database tables and test data.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import load_config
from core.database import DatabaseManager


# Sample setup queries
SETUP_QUERIES = [
    """
    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Users')
    CREATE TABLE Users (
        id INT IDENTITY(1,1) PRIMARY KEY,
        username NVARCHAR(50) NOT NULL UNIQUE,
        email NVARCHAR(100) NOT NULL,
        created_at DATETIME2 DEFAULT GETDATE(),
        is_active BIT DEFAULT 1
    )
    """,
    """
    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Products')
    CREATE TABLE Products (
        id INT IDENTITY(1,1) PRIMARY KEY,
        name NVARCHAR(100) NOT NULL,
        description NVARCHAR(500),
        price DECIMAL(10,2) NOT NULL,
        category_id INT,
        created_at DATETIME2 DEFAULT GETDATE(),
        is_available BIT DEFAULT 1
    )
    """,
    """
    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Orders')
    CREATE TABLE Orders (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL,
        total_amount DECIMAL(10,2) NOT NULL,
        order_date DATETIME2 DEFAULT GETDATE(),
        status NVARCHAR(20) DEFAULT 'pending'
    )
    """
]

# Sample test data
TEST_DATA_QUERIES = [
    """
    IF NOT EXISTS (SELECT * FROM Users WHERE username = 'testuser1')
    INSERT INTO Users (username, email) VALUES 
    ('testuser1', 'test1@example.com'),
    ('testuser2', 'test2@example.com'),
    ('testuser3', 'test3@example.com')
    """,
    """
    IF NOT EXISTS (SELECT * FROM Products WHERE name = 'Test Product 1')
    INSERT INTO Products (name, description, price) VALUES 
    ('Test Product 1', 'Description for test product 1', 19.99),
    ('Test Product 2', 'Description for test product 2', 29.99),
    ('Test Product 3', 'Description for test product 3', 39.99)
    """,
    """
    IF NOT EXISTS (SELECT * FROM Orders WHERE user_id = 1)
    INSERT INTO Orders (user_id, total_amount, status) VALUES 
    (1, 19.99, 'completed'),
    (2, 29.99, 'pending'),
    (1, 39.99, 'completed')
    """
]


async def setup_database(create_test_data: bool = False):
    """Set up the database with sample tables and optionally test data."""
    try:
        # Load configuration
        config = load_config()
        
        # Initialize database manager
        db_manager = DatabaseManager(config.database, None)
        
        print("Setting up database tables...")
        
        # Execute setup queries
        for i, query in enumerate(SETUP_QUERIES, 1):
            print(f"Executing setup query {i}/{len(SETUP_QUERIES)}...")
            result = await db_manager.execute_query(query)
            if not result.get("success", True):
                print(f"Warning: Setup query {i} failed: {result.get('error')}")
            else:
                print(f"Setup query {i} completed successfully")
        
        if create_test_data:
            print("\nInserting test data...")
            for i, query in enumerate(TEST_DATA_QUERIES, 1):
                print(f"Executing test data query {i}/{len(TEST_DATA_QUERIES)}...")
                result = await db_manager.execute_query(query)
                if not result.get("success", True):
                    print(f"Warning: Test data query {i} failed: {result.get('error')}")
                else:
                    print(f"Test data query {i} completed successfully")
        
        print("\nDatabase setup completed successfully!")
        
        # Test the setup by listing tables
        print("\nVerifying setup - listing tables:")
        tables_result = await db_manager.execute_query(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'"
        )
        
        if tables_result.get("rows"):
            for row in tables_result["rows"]:
                print(f"  - {row[0]}")
        else:
            print("  No tables found")
            
    except Exception as e:
        print(f"Error during database setup: {e}")
        sys.exit(1)


async def main():
    """Main setup function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Set up MSSQL MCP Server database")
    parser.add_argument(
        "--test-data", 
        action="store_true", 
        help="Include test data in the setup"
    )
    parser.add_argument(
        "--config", 
        help="Configuration file path"
    )
    parser.add_argument(
        "--profile", 
        help="Configuration profile (development, staging, production)"
    )
    
    args = parser.parse_args()
    
    # Set environment variables if provided
    if args.config:
        os.environ["MCP_CONFIG_FILE"] = args.config
    if args.profile:
        os.environ["MCP_PROFILE"] = args.profile
    
    await setup_database(create_test_data=args.test_data)


if __name__ == "__main__":
    asyncio.run(main())
