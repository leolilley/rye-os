<!-- rye:validated:2026-02-03T07:29:34Z:c96e30cebcb633f9053100fad222e6465a81399503429cb50b74e9265b739f96 -->
# Create Simple Directive

Create minimal directives with essential fields only.

```xml
<directive name="create_directive" version="1.0.0">
  <metadata>
    <description>Create simple directives with minimal required fields.</description>
    <category>rye/core</category>
    <author>rye-os</author>
  </metadata>

  <inputs>
    <input name="name" type="string" required="true">
      Directive name in snake_case (e.g., "deploy_app", "create_component")
    </input>
    <input name="category" type="string" required="true">
      Directory path relative to .ai/directives/ (e.g., "workflows", "testing")
    </input>
    <input name="description" type="string" required="true">
      What does this directive do? Be specific and actionable.
    </input>
    <input name="process_steps" type="string" required="false">
      Brief summary of process steps (bullet points)
    </input>
  </inputs>

  <process>
    <step name="validate_inputs">
      <description>Validate all required inputs</description>
      <action><![CDATA[
1. name must be snake_case alphanumeric
2. category must be non-empty string (path relative to .ai/directives/)
3. description must be non-empty

Halt if any validation fails.
      ]]></action>
    </step>

    <step name="determine_file_path">
      <description>Calculate file path from category</description>
      <action><![CDATA[
File location is: .ai/directives/{category}/{name}.md

Examples:
- category="workflows", name="deploy_app" → .ai/directives/workflows/deploy_app.md
- category="testing" → .ai/directives/testing/{name}.md

Create parent directories as needed.
      ]]></action>
    </step>

    <step name="create_directive_content">
      <description>Generate minimal directive markdown file</description>
      <action><![CDATA[
Create .md file with structure:

# {Title from name}

{description}

```xml
<directive name="{name}" version="1.0.0">
  <metadata>
    <description>{description}</description>
    <category>{category}</category>
    <author>user</author>
  </metadata>

  <process>
    <step name="step_1">
      <description>What this step does</description>
      <action><![CDATA[
Detailed action with commands/instructions
      ]]></action>
    </step>
  </process>

  <success_criteria>
    <criterion>Measurable success condition</criterion>
  </success_criteria>

  <outputs>
    <success>Success message and next steps</success>
    <failure>Failure message and common fixes</failure>
  </outputs>
</directive>
```

CRITICAL:
- All XML must be well-formed (matching tags, proper escaping)
- Use CDATA sections for multi-line action blocks: <![CDATA[ ... ]]>
- Minimal structure: only name, version, description, category, author
- For advanced features (model tiers, permissions, cost), see create_advanced_directive
      ]]></action>
    </step>

    <step name="validate_and_sign">
      <description>Validate XML and generate signature</description>
      <action><![CDATA[
Run mcp_rye sign to validate and sign the directive:

mcp_rye_execute(
  item_type="directive",
  action="sign",
  item_id="{name}",
  parameters={"location": "project"},
  project_path="{project_path}"
)

This validates XML syntax and creates a signature comment at top of file.

If validation fails: fix XML errors and re-run sign.
Common errors: mismatched tags, unescaped special chars, missing CDATA
      ]]></action>
      <verification>
        <check>File has signature comment at top</check>
        <check>No XML parse errors</check>
        <check>Required metadata fields present</check>
      </verification>
    </step>
  </process>

  <success_criteria>
    <criterion>Directive file created at correct path (.ai/directives/{category}/{name}.md)</criterion>
    <criterion>All required XML elements present and well-formed</criterion>
    <criterion>Metadata includes only name, version, description, category, author</criterion>
    <criterion>Signature validation comment added to file</criterion>
    <criterion>Directive is discoverable via search</criterion>
  </success_criteria>

  <outputs>
    <success><![CDATA[
✓ Created directive: {name}
Location: .ai/directives/{category}/{name}.md
Version: 1.0.0

Note: This is a minimal directive. For advanced features (model tiers, permissions, cost tracking), use create_advanced_directive.

Next steps:
- Test: Run directive {name}
- Edit: Update steps and re-sign
- Link: Reference from other directives (relationships.requires/suggests)
- Advanced: See create_advanced_directive for power user features
    ]]></success>
    <failure><![CDATA[
✗ Failed to create directive: {name}
Error: {error}

Common fixes:
- name must be snake_case (create_directive, not CreateDirective)
- category must match target directory path
- XML must be well-formed (matching tags, proper escaping)
- Use CDATA for multi-line blocks: <![CDATA[ ... ]]>
- All required metadata must be present (name, version, description, category, author)
    ]]></failure>
  </outputs>
</directive>
```
