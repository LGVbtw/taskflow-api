from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0011_tasktype_hierarchy'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskRelation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('link_type', models.CharField(choices=[('blocks', 'Bloque'), ('depends', 'Dépend'), ('relates', 'Relatif à')], max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('dst_task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='relations_in', to='tasks.task')),
                ('src_task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='relations_out', to='tasks.task')),
            ],
        ),
        migrations.AddConstraint(
            model_name='taskrelation',
            constraint=models.UniqueConstraint(fields=('src_task', 'dst_task', 'link_type'), name='unique_task_relation'),
        ),
    ]
