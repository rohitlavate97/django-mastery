from django.db.migrations.operations.base import Operation

class SafeAddIndexConcurrently(Operation):
    """
    A migration operation to safely add an index concurrently in PostgreSQL.
    """
    atomic = False

    def __init__(self, model_name, index):
        self.model_name = model_name
        self.index = index

    def state_forwards(self, app_label, state):
        model_state = state.models[app_label, self.model_name.lower()]
        model_state.options['indexes'] = model_state.options.get('indexes', []) + [self.index]
        state.reload_model(app_label, self.model_name.lower())

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        
        # PostgreSQL specific: SET lock_timeout
        schema_editor.execute("SET lock_timeout = '2s';")
        
        # Generate the SQL for the index
        sql = self.index.create_sql(model, schema_editor)
        
        # Inject CONCURRENTLY if not present (simplified for exercise purposes)
        # Note: In Django 3.0+, AddIndexConcurrently exists but runs inside atomic by default if not careful,
        # or requires specific atomic=False. We are building a raw SQL executor here.
        if "CONCURRENTLY" not in sql.upper():
            sql = sql.replace("CREATE INDEX", "CREATE INDEX CONCURRENTLY", 1)
            
        try:
            schema_editor.execute(sql)
        finally:
            schema_editor.execute("RESET lock_timeout;")

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.model_name)
        sql = self.index.remove_sql(model, schema_editor)
        schema_editor.execute(sql)

    def describe(self):
        return f"Safely add concurrent index {self.index.name} on {self.model_name}"
