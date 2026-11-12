"""Cloud configuration/auth/TLS tests; no credentials, network broker or live DB."""
from dataclasses import replace
import io
import hashlib
from pathlib import Path
import tempfile
import ssl
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from backend.config import Settings
from backend.mqtt_ingest import Ingestor
from backend.postgres import Connection, POSTGRES_SCHEMA, Row
from backend.db import Database
from backend.tools.import_sqlite_history import export_sql
from support import http_server, test_settings, request, validated


class CloudTests(unittest.TestCase):
    def test_cloud_fails_closed_and_secrets_are_not_repr(self):
        values = dict(database_url='postgresql://ep-parking-pooler.us-east-2.aws.neon.tech/parking?sslmode=verify-full',
            database_expected_host='ep-parking-pooler.us-east-2.aws.neon.tech',
            mqtt_tls=True, mqtt_username='fixture', mqtt_password='fixture',
            api_bearer_token='x'*32, deployment_mode='cloud')
        settings = Settings(**values)
        for key, bad in [('database_url',''),('mqtt_tls',False),('mqtt_enabled',False),
                         ('database_expected_host',''),
                         ('mqtt_username',''),('mqtt_password',''),('api_bearer_token','short')]:
            with self.subTest(key=key), self.assertRaises(ValueError): replace(settings, **{key:bad})
        self.assertNotIn(settings.database_url, repr(settings))
        self.assertNotIn(settings.api_bearer_token, repr(settings))
        for url in ('sqlite:///x','postgresql://example.invalid/x?sslmode=disable',
                    'postgresql://example.invalid/x?sslmode=require'):
            with self.assertRaises(ValueError): Settings(database_url=url)

    def test_cloud_rejects_another_project_hostname_before_any_database_access(self):
        environment = {'DEPLOYMENT_MODE':'cloud', 'DATABASE_EXPECTED_HOST':'ep-parking-pooler.us-east-2.aws.neon.tech',
            'DATABASE_URL':'postgresql://ep-unrelated-pooler.us-east-2.aws.neon.tech/parking?sslmode=verify-full',
            'MQTT_TLS':'true','MQTT_USERNAME':'fixture','MQTT_PASSWORD':'fixture','API_BEARER_TOKEN':'x'*32}
        with patch.dict('os.environ',environment), patch('backend.postgres.PostgresDatabase.raw_connection') as connection:
            with self.assertRaisesRegex(ValueError,'DATABASE_EXPECTED_HOST'): Settings.from_env()
            connection.assert_not_called()
            environment['DATABASE_URL']='postgresql://ep-parking-pooler.us-east-2.aws.neon.tech/parking?sslmode=verify-full'
            with patch.dict('os.environ',environment):
                self.assertEqual(Settings.from_env().database_expected_host,environment['DATABASE_EXPECTED_HOST'])

    def test_tls_context_verifies_certificate_and_hostname(self):
        with test_settings(mqtt_tls=True) as settings:
            client = Mock()
            Ingestor(settings, Mock(), client=client)
            context = client.tls_set_context.call_args.args[0]
            self.assertTrue(context.check_hostname)
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertGreaterEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
            client.tls_insecure_set.assert_not_called()

    def test_auth_protects_api_docs_health_and_forecasts_but_liveness_is_public(self):
        with test_settings(api_bearer_token='isolated-test-value') as settings, http_server(settings) as (app,base):
            for path in ('/slots','/history','/stats','/health','/openapi.json','/predictions/persistence-live'):
                with self.subTest(path=path): self.assertEqual(request(base,path)[0],401)
            self.assertEqual(request(base,'/livez'),(200,{'status':'ok'}))
            for token, status in [('wrong',401),('isolated-test-value',200)]:
                req = Request(base+'/predictions/persistence-live',headers={'Authorization':'Bearer '+token})
                try:
                    response = urlopen(req,timeout=5)
                except HTTPError as error:
                    response = error
                with response:
                    self.assertEqual(response.status,status)
                    self.assertEqual(response.headers['Cache-Control'],'no-store')

    def test_fixed_sql_translation_keeps_values_bound_and_returns_ids(self):
        raw = Mock()
        raw.execute.return_value.fetchone.return_value = {'id':7}
        value = 'not-interpolated'
        result = Connection(raw).execute('INSERT INTO telemetry_messages(fingerprint) VALUES (?)',(value,))
        raw.execute.assert_called_once_with('INSERT INTO telemetry_messages(fingerprint) VALUES (%s) RETURNING id',(value,))
        self.assertEqual(result.lastrowid,7)
        Connection(raw).execute('BEGIN IMMEDIATE')
        self.assertEqual(raw.execute.call_args.args[0],'SELECT pg_advisory_xact_lock(1397771058)')
        self.assertIn('sequence BIGINT',POSTGRES_SCHEMA)
        self.assertEqual(Row(n=12)[0],12)

    def test_missing_local_database_does_not_create_project_file(self):
        with patch.dict('os.environ',{'DATABASE_URL':'postgresql://example.invalid/parking','LOCALAPPDATA':'','DATABASE_PATH':''}):
            self.assertIsNone(Settings.from_env().database_path)

    def test_driver_free_export_preserves_source_and_guards_cloud_history(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'export.db'
            database=Database(source);database.initialize();database.persist(validated())
            before=hashlib.sha256(source.read_bytes()).hexdigest()
            script,result=export_sql(source)
            self.assertEqual(result['source_sha256'],before)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
            self.assertEqual(result['copied_rows']['occupancy_observations'],4)
            self.assertIn("RAISE EXCEPTION 'Destination must be recognized and empty'",script)
            self.assertTrue(script.endswith('COMMIT;\n'))


if __name__ == '__main__': unittest.main(verbosity=2)
