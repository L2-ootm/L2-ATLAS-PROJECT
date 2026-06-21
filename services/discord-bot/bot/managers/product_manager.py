"""
L2 SYSTEMS // Product Manager
Handles persistence for E-commerce products and user carts.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)

class ProductManager:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.products_file = self.data_dir / "products.json"
        self.carts_file = self.data_dir / "carts.json"
        
        # In-memory storage
        self.products: Dict[str, Dict] = {} # {id: {data}}
        self.carts: Dict[str, List[str]] = {} # {user_id: [product_ids]}
        
        self._load_data()

    def _load_data(self):
        """Load data from JSON files."""
        # Load Products
        if self.products_file.exists():
            try:
                with open(self.products_file, "r", encoding='utf-8') as f:
                    self.products = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load products: {e}")
                self.products = {}
        
        # Load Carts
        if self.carts_file.exists():
            try:
                with open(self.carts_file, "r", encoding='utf-8') as f:
                    self.carts = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load carts: {e}")
                self.carts = {}

    def _save_products(self):
        try:
            with open(self.products_file, "w", encoding='utf-8') as f:
                json.dump(self.products, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save products: {e}")

    def _save_carts(self):
        try:
            with open(self.carts_file, "w", encoding='utf-8') as f:
                json.dump(self.carts, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save carts: {e}")

    # PRODUCT MANAGEMENT
    def add_product(self, product_id: str, name: str, price: float, description: str, stock: int = -1, image_url: str = None) -> bool:
        """Add or update a product."""
        self.products[product_id] = {
            "id": product_id,
            "name": name,
            "price": price,
            "description": description,
            "stock": stock, # -1 = infinite
            "image_url": image_url
        }
        self._save_products()
        return True

    def get_product(self, product_id: str) -> Optional[Dict]:
        return self.products.get(product_id)

    def get_all_products(self) -> List[Dict]:
        return list(self.products.values())

    def delete_product(self, product_id: str) -> bool:
        if product_id in self.products:
            del self.products[product_id]
            self._save_products()
            return True
        return False

    # CART MANAGEMENT
    def add_to_cart(self, user_id: Union[int, str], product_id: str) -> bool:
        user_id = str(user_id)
        if product_id not in self.products:
            return False
        
        if user_id not in self.carts:
            self.carts[user_id] = []
        
        self.carts[user_id].append(product_id)
        self._save_carts()
        return True

    def remove_from_cart(self, user_id: Union[int, str], product_id: str) -> bool:
        user_id = str(user_id)
        if user_id in self.carts and product_id in self.carts[user_id]:
            self.carts[user_id].remove(product_id)
            if not self.carts[user_id]:
                del self.carts[user_id]
            self._save_carts()
            return True
        return False

    def clear_cart(self, user_id: Union[int, str]):
        user_id = str(user_id)
        if user_id in self.carts:
            del self.carts[user_id]
            self._save_carts()

    def get_cart(self, user_id: Union[int, str]) -> List[Dict]:
        """Return list of product objects in cart."""
        user_id = str(user_id)
        if user_id not in self.carts:
            return []
        
        items = []
        for pid in self.carts[user_id]:
            prod = self.get_product(pid)
            if prod:
                items.append(prod)
        return items

    def get_cart_total(self, user_id: Union[int, str]) -> float:
        items = self.get_cart(user_id)
        return sum(item['price'] for item in items)
