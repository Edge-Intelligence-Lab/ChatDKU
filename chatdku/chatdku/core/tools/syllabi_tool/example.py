from setup import DB


class Product:
    def __init__(self, id, name, price, available, sid):
        self.id = id
        self.name = name
        self.price = price
        self.available = available
        self.sid = sid

    @staticmethod
    def get(id):
        db = DB()
        rows = db.execute(
            """
            SELECT id, name, price, available, sid
            FROM Products
            WHERE id = :id
            """,
            id=id,
        )
        return Product(*(rows[0])) if rows else None

    @staticmethod
    def get_all(available=True):
        db = DB()
        rows = db.execute(
            """
            SELECT id, name, price, available, sid
            FROM Products
            WHERE available = :available
            """,
            available=available,
        )
        return [Product(*row) for row in rows]

    @staticmethod
    def get_by_seller_id(sid):
        db = DB()
        rows = db.execute(
            """
            SELECT id, name, price, available, sid
            FROM Products
            WHERE sid = :sid
            """,
            sid=sid,
        )
        return [Product(*row) for row in rows]

    @staticmethod
    def get_k_most_expensive(k):
        db = DB()
        rows = db.execute(
            """
            SELECT id, name, price, available, sid
            FROM Products
            ORDER BY price DESC
            LIMIT :k
            """,
            k=k,
        )
        return [Product(*row) for row in rows]
